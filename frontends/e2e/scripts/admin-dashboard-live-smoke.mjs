import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../..");
const screenshotDir = resolve(repoRoot, "docs/diag/screenshots");
const adminBaseUrl = (process.env.ADMIN_PORTAL_URL ?? "http://localhost/admin/").replace(/\/+$/, "");
const roleTokens = JSON.parse(process.env.ROLE_TOKENS_JSON ?? "{}");
const outputPath = process.env.ADMIN_DASHBOARD_SMOKE_OUTPUT
  ? resolve(process.cwd(), process.env.ADMIN_DASHBOARD_SMOKE_OUTPUT)
  : resolve(repoRoot, "docs/diag/admin-dashboard-live-smoke.json");

const storageKey = "neft_admin_access_token";
const screenshotOptions = { fullPage: true };
const staleRoutePrefixes = ["/billing", "/money", "/fleet", "/subscriptions", "/operations", "/explain"];

const scenarios = [
  {
    role: "NEFT_OPS",
    path: "/",
    screenshot: "admin-dashboard-ops.png",
    headings: ["Admin operator console"],
    presentLinks: ["Rules Sandbox", "Risk Rules", "Policy Center", "Geo Analytics", "Ops KPI"],
    absentLinks: ["Revenue"],
  },
  {
    role: "NEFT_FINANCE",
    path: "/",
    screenshot: "admin-dashboard-finance.png",
    headings: ["Admin operator console"],
    presentLinks: ["Finance", "Revenue"],
    absentLinks: ["Rules Sandbox", "Risk Rules", "Policy Center"],
  },
  {
    role: "NEFT_SUPPORT",
    path: "/",
    screenshot: "admin-dashboard-support.png",
    headings: ["Admin operator console"],
    presentLinks: ["Cases", "Onboarding"],
    absentLinks: ["Revenue", "Rules Sandbox", "Risk Rules", "Policy Center"],
  },
  {
    role: "NEFT_SALES",
    path: "/crm/tariffs",
    screenshot: "admin-shell-crm-tariffs.png",
    headings: ["CRM"],
    presentLinks: ["CRM", "Revenue"],
    absentLinks: ["Rules Sandbox", "Risk Rules", "Policy Center"],
  },
  {
    role: "NEFT_LEGAL",
    path: "/legal/partners",
    screenshot: "admin-shell-legal-partners.png",
    headings: ["Legal"],
    presentLinks: ["Legal"],
    absentLinks: ["Revenue", "Rules Sandbox", "Risk Rules", "Policy Center"],
  },
];

function assertToken(role) {
  const token = roleTokens[role];
  if (!token || typeof token !== "string") {
    throw new Error(`Missing token for ${role}`);
  }
  return token;
}

async function visibleRole(page, role, name) {
  return page.getByRole(role, { name }).first().isVisible().catch(() => false);
}

async function probeScenario(browser, spec) {
  const token = assertToken(spec.role);
  const context = await browser.newContext({ viewport: { width: 1440, height: 980 } });
  const apiResponses = [];
  const consoleMessages = [];
  const pageErrors = [];

  await context.addInitScript(
    ({ storageKey, token, role }) => {
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          accessToken: token,
          email: `${role.toLowerCase()}@neft.test`,
          roles: [role],
          expiresAt: Date.now() + 30 * 60 * 1000,
        }),
      );
    },
    { storageKey, token, role: spec.role },
  );

  const page = await context.newPage();
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleMessages.push({ type: message.type(), text: message.text() });
    }
  });
  page.on("pageerror", (error) => {
    pageErrors.push(error.message);
  });
  page.on("response", async (response) => {
    const url = response.url();
    if (url.includes("/api/core/v1/admin/me")) {
      apiResponses.push({
        url,
        status: response.status(),
        contentType: response.headers()["content-type"] ?? null,
      });
    }
  });

  const routeUrl = `${adminBaseUrl}${spec.path.startsWith("/") ? spec.path : `/${spec.path}`}`;
  await page.goto(routeUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
  await page.waitForTimeout(800);

  const screenshotPath = resolve(screenshotDir, spec.screenshot);
  await page.screenshot({ path: screenshotPath, ...screenshotOptions });

  const bodyText = (await page.locator("body").innerText().catch(() => "")).replace(/\s+/g, " ").trim();
  const links = await page.locator("a[href]").evaluateAll((anchors) =>
    anchors.map((anchor) => ({
      text: (anchor.textContent ?? "").replace(/\s+/g, " ").trim(),
      href: anchor.getAttribute("href") ?? "",
    })),
  );
  const hasErrorOverlay = await page
    .locator("[data-nextjs-dialog], .vite-error-overlay, #webpack-dev-server-client-overlay")
    .first()
    .isVisible()
    .catch(() => false);
  const meResponse = apiResponses.find((item) => item.url.includes("/me"));
  const staleLinks = links.filter((link) => staleRoutePrefixes.some((prefix) => link.href.startsWith(prefix)));
  const headingResults = [];
  const presentLinkResults = [];
  const absentLinkResults = [];

  for (const heading of spec.headings) {
    headingResults.push({ heading, visible: await visibleRole(page, "heading", heading) });
  }
  for (const link of spec.presentLinks) {
    presentLinkResults.push({ link, visible: await visibleRole(page, "link", link) });
  }
  for (const link of spec.absentLinks) {
    absentLinkResults.push({ link, visible: await visibleRole(page, "link", link) });
  }

  if (!bodyText.length) {
    throw new Error(`${spec.role} ${spec.path}: blank page`);
  }
  if (hasErrorOverlay) {
    throw new Error(`${spec.role} ${spec.path}: framework error overlay visible`);
  }
  if (pageErrors.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: page errors: ${pageErrors.join(" | ")}`);
  }
  if (consoleMessages.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: console messages: ${JSON.stringify(consoleMessages)}`);
  }
  if (!meResponse || meResponse.status !== 200) {
    throw new Error(`${spec.role} ${spec.path}: expected /admin/me 200, got ${meResponse?.status ?? "missing"}`);
  }
  const missingHeadings = headingResults.filter((item) => !item.visible).map((item) => item.heading);
  if (missingHeadings.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: missing headings ${missingHeadings.join(", ")}`);
  }
  const missingLinks = presentLinkResults.filter((item) => !item.visible).map((item) => item.link);
  if (missingLinks.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: missing links ${missingLinks.join(", ")}`);
  }
  const unexpectedLinks = absentLinkResults.filter((item) => item.visible).map((item) => item.link);
  if (unexpectedLinks.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: unexpected links ${unexpectedLinks.join(", ")}`);
  }
  if (staleLinks.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: stale links ${JSON.stringify(staleLinks)}`);
  }

  await context.close();
  return {
    role: spec.role,
    path: spec.path,
    url: routeUrl,
    bodySnippet: bodyText.slice(0, 220),
    meStatus: meResponse.status,
    headings: headingResults,
    presentLinks: presentLinkResults,
    absentLinks: absentLinkResults,
    staleLinks,
    consoleMessages,
    screenshot: screenshotPath,
  };
}

mkdirSync(screenshotDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  const results = [];
  for (const spec of scenarios) {
    results.push(await probeScenario(browser, spec));
  }
  const payload = {
    checked_at: new Date().toISOString(),
    admin_base_url: adminBaseUrl,
    stale_route_prefixes: staleRoutePrefixes,
    results,
  };
  writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(payload, null, 2));
} finally {
  await browser.close();
}

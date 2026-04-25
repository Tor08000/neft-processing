import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../..");
const screenshotDir = resolve(repoRoot, "docs/diag/screenshots");
const adminBaseUrl = (process.env.ADMIN_PORTAL_URL ?? "http://localhost/admin/").replace(/\/+$/, "");
const roleTokens = JSON.parse(process.env.ROLE_TOKENS_JSON ?? "{}");
const outputPath = process.env.ADMIN_REVENUE_SMOKE_OUTPUT
  ? resolve(process.cwd(), process.env.ADMIN_REVENUE_SMOKE_OUTPUT)
  : resolve(repoRoot, "docs/diag/admin-revenue-live-smoke.json");

const roles = [
  { role: "NEFT_FINANCE", expected: "allowed", screenshot: "admin-revenue-finance.png" },
  { role: "NEFT_SALES", expected: "allowed", screenshot: "admin-revenue-sales.png" },
  { role: "PLATFORM_ADMIN", expected: "forbidden", screenshot: "admin-revenue-platform-forbidden.png" },
  { role: "NEFT_SUPPORT", expected: "forbidden", screenshot: "admin-revenue-support-forbidden.png" },
];

const storageKey = "neft_admin_access_token";
const expectedPath = "/finance/revenue";
const screenshotOptions = { fullPage: true };

function assertToken(role) {
  const token = roleTokens[role];
  if (!token || typeof token !== "string") {
    throw new Error(`Missing token for ${role}`);
  }
  return token;
}

async function visibleText(page, text) {
  return page.getByText(text, { exact: false }).first().isVisible().catch(() => false);
}

async function visibleRole(page, role, name) {
  return page.getByRole(role, { name }).first().isVisible().catch(() => false);
}

async function probeRole(browser, spec) {
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
    if (!url.includes("/api/core/v1/admin/")) {
      return;
    }
    if (!url.includes("/me") && !url.includes("/revenue/summary") && !url.includes("/revenue/overdue")) {
      return;
    }
    apiResponses.push({
      url,
      status: response.status(),
      contentType: response.headers()["content-type"] ?? null,
    });
  });

  const routeUrl = `${adminBaseUrl}${expectedPath}`;
  await page.goto(routeUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
  await page.waitForTimeout(800);

  const screenshotPath = resolve(screenshotDir, spec.screenshot);
  await page.screenshot({ path: screenshotPath, ...screenshotOptions });

  const bodyText = (await page.locator("body").innerText().catch(() => "")).replace(/\s+/g, " ").trim();
  const hasErrorOverlay = await page
    .locator("[data-nextjs-dialog], .vite-error-overlay, #webpack-dev-server-client-overlay")
    .first()
    .isVisible()
    .catch(() => false);
  const hasContent = bodyText.length > 0;
  const hasRevenueHeading = await visibleRole(page, "heading", "Revenue");
  const hasForbidden = await visibleText(page, "FORBIDDEN_ROLE");
  const hasRevenueNav = await visibleRole(page, "link", "Revenue");
  const revenueSummary = apiResponses.find((item) => item.url.includes("/revenue/summary"));
  const revenueOverdue = apiResponses.find((item) => item.url.includes("/revenue/overdue"));
  const meResponse = apiResponses.find((item) => item.url.includes("/me"));

  if (!hasContent) {
    throw new Error(`${spec.role}: blank page`);
  }
  if (hasErrorOverlay) {
    throw new Error(`${spec.role}: framework error overlay visible`);
  }
  if (pageErrors.length > 0) {
    throw new Error(`${spec.role}: page errors: ${pageErrors.join(" | ")}`);
  }

  if (spec.expected === "allowed") {
    if (!hasRevenueHeading || hasForbidden || !hasRevenueNav) {
      throw new Error(
        `${spec.role}: expected revenue page, got heading=${hasRevenueHeading} forbidden=${hasForbidden} nav=${hasRevenueNav}`,
      );
    }
    if (!revenueSummary || revenueSummary.status !== 200) {
      throw new Error(`${spec.role}: expected /revenue/summary 200, got ${revenueSummary?.status ?? "missing"}`);
    }
    if (!revenueOverdue || revenueOverdue.status !== 200) {
      throw new Error(`${spec.role}: expected /revenue/overdue 200, got ${revenueOverdue?.status ?? "missing"}`);
    }
  } else {
    if (!hasForbidden || hasRevenueHeading || hasRevenueNav) {
      throw new Error(
        `${spec.role}: expected forbidden without nav, got forbidden=${hasForbidden} heading=${hasRevenueHeading} nav=${hasRevenueNav}`,
      );
    }
    if (revenueSummary || revenueOverdue) {
      throw new Error(`${spec.role}: forbidden role still issued revenue API requests`);
    }
  }

  await context.close();
  return {
    role: spec.role,
    expected: spec.expected,
    url: routeUrl,
    bodySnippet: bodyText.slice(0, 220),
    hasRevenueHeading,
    hasForbidden,
    hasRevenueNav,
    meStatus: meResponse?.status ?? null,
    revenueSummaryStatus: revenueSummary?.status ?? null,
    revenueOverdueStatus: revenueOverdue?.status ?? null,
    consoleMessages,
    screenshot: screenshotPath,
  };
}

mkdirSync(screenshotDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  const results = [];
  for (const spec of roles) {
    results.push(await probeRole(browser, spec));
  }
  const payload = {
    checked_at: new Date().toISOString(),
    admin_base_url: adminBaseUrl,
    route: expectedPath,
    results,
  };
  writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(payload, null, 2));
} finally {
  await browser.close();
}

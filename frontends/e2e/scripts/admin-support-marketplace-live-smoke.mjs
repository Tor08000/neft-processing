import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../..");
const screenshotDir = resolve(repoRoot, "docs/diag/screenshots");
const adminBaseUrl = (process.env.ADMIN_PORTAL_URL ?? "http://localhost/admin/").replace(/\/+$/, "");
const roleTokens = JSON.parse(process.env.ROLE_TOKENS_JSON ?? "{}");
const outputPath = process.env.ADMIN_SUPPORT_MARKETPLACE_SMOKE_OUTPUT
  ? resolve(process.cwd(), process.env.ADMIN_SUPPORT_MARKETPLACE_SMOKE_OUTPUT)
  : resolve(repoRoot, "docs/diag/admin-support-marketplace-live-smoke.json");

const storageKey = "neft_admin_access_token";
const screenshotOptions = { fullPage: true };
const apiOrigin = new URL(adminBaseUrl).origin;

const scenarios = [
  {
    role: "NEFT_SUPPORT",
    path: "/cases?queue=SUPPORT",
    screenshot: "admin-cases-support.png",
    textIncludes: ["Cases", "Support & Incident Inbox"],
    presentLinks: ["Cases", "Marketplace", "Onboarding"],
    absentLinks: ["Revenue", "Rules Sandbox", "Risk Rules", "Policy Center"],
    expectedApi: [
      { contains: "/api/core/v1/admin/me", status: 200 },
      { contains: "/api/core/cases", status: 200 },
    ],
  },
  {
    role: "NEFT_FINANCE",
    path: "/cases?queue=SUPPORT",
    screenshot: "admin-cases-finance-readonly.png",
    textIncludes: ["Cases", "Support & Incident Inbox"],
    presentLinks: ["Cases", "Finance", "Revenue"],
    absentLinks: ["Marketplace", "Rules Sandbox", "Risk Rules", "Policy Center"],
    expectedApi: [
      { contains: "/api/core/v1/admin/me", status: 200 },
      { contains: "/api/core/cases", status: 200 },
    ],
  },
  {
    role: "NEFT_SUPPORT",
    path: "/marketplace/moderation",
    screenshot: "admin-marketplace-support-read.png",
    textIncludes: ["Marketplace", "Moderation queue"],
    presentLinks: ["Cases", "Marketplace"],
    absentLinks: ["Revenue", "Rules Sandbox", "Risk Rules", "Policy Center"],
    expectedApi: [
      { contains: "/api/core/v1/admin/me", status: 200 },
      { contains: "/api/core/v1/admin/marketplace/moderation/queue", status: 200 },
    ],
  },
  {
    role: "NEFT_FINANCE",
    path: "/marketplace/moderation",
    screenshot: "admin-marketplace-finance-forbidden.png",
    headings: ["FORBIDDEN_ROLE"],
    textIncludes: ["FORBIDDEN_ROLE"],
    presentLinks: ["Finance", "Revenue"],
    absentLinks: ["Marketplace"],
    expectedApi: [{ contains: "/api/core/v1/admin/me", status: 200 }],
    forbiddenApiIncludes: ["/api/core/v1/admin/marketplace/moderation/queue"],
  },
  {
    role: "NEFT_SUPPORT",
    path: "/marketplace/moderation/product/00000000-0000-0000-0000-000000000999",
    screenshot: "admin-marketplace-support-detail-readonly.png",
    textIncludes: ["Marketplace", "READ-ONLY MODERATION", "Failed to load moderation detail"],
    absentButtons: ["Approve", "Reject"],
    expectedApi: [
      { contains: "/api/core/v1/admin/me", status: 200 },
      { contains: "/api/core/v1/admin/marketplace/products/00000000-0000-0000-0000-000000000999", status: 404 },
    ],
  },
];

const directApiChecks = [
  {
    role: "NEFT_FINANCE",
    method: "GET",
    path: "/api/core/v1/admin/products",
    expectedStatus: 403,
  },
  {
    role: "NEFT_FINANCE",
    method: "GET",
    path: "/api/core/v1/admin/marketplace/orders",
    expectedStatus: 403,
  },
  {
    role: "NEFT_FINANCE",
    method: "GET",
    path: "/api/core/v1/admin/marketplace/sponsored/campaigns",
    expectedStatus: 403,
  },
  {
    role: "NEFT_SUPPORT",
    method: "POST",
    path: "/api/core/v1/admin/partners/partner-1/verify",
    payload: { status: "VERIFIED", reason: "runtime probe" },
    expectedStatus: 403,
  },
  {
    role: "NEFT_SUPPORT",
    method: "POST",
    path: "/api/core/v1/admin/marketplace/orders/order-1/settlement-override",
    payload: {
      gross_amount: "100.00",
      platform_fee: "10.00",
      penalties: "0.00",
      partner_net: "90.00",
      currency: "RUB",
      reason: "runtime probe",
    },
    expectedStatus: 403,
  },
  {
    role: "NEFT_SUPPORT",
    method: "PATCH",
    path: "/api/core/v1/admin/marketplace/sponsored/campaigns/campaign-1/status",
    payload: { status: "PAUSED", reason: "runtime probe" },
    expectedStatus: 403,
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
  page.on("response", (response) => {
    const url = response.url();
    if (url.includes("/api/core/v1/admin") || url.includes("/api/core/cases")) {
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
  const hasErrorOverlay = await page
    .locator("[data-nextjs-dialog], .vite-error-overlay, #webpack-dev-server-client-overlay")
    .first()
    .isVisible()
    .catch(() => false);

  if (!bodyText.length) {
    throw new Error(`${spec.role} ${spec.path}: blank page`);
  }
  if (hasErrorOverlay) {
    throw new Error(`${spec.role} ${spec.path}: framework error overlay visible`);
  }
  if (pageErrors.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: page errors: ${pageErrors.join(" | ")}`);
  }
  const headingResults = [];
  for (const heading of spec.headings ?? []) {
    headingResults.push({ heading, visible: await visibleRole(page, "heading", heading) });
  }
  const missingHeadings = headingResults.filter((item) => !item.visible).map((item) => item.heading);
  if (missingHeadings.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: missing headings ${missingHeadings.join(", ")}`);
  }

  for (const text of spec.textIncludes ?? []) {
    if (!bodyText.includes(text)) {
      throw new Error(`${spec.role} ${spec.path}: missing text ${text}`);
    }
  }

  const presentLinkResults = [];
  for (const link of spec.presentLinks ?? []) {
    presentLinkResults.push({ link, visible: await visibleRole(page, "link", link) });
  }
  const missingLinks = presentLinkResults.filter((item) => !item.visible).map((item) => item.link);
  if (missingLinks.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: missing links ${missingLinks.join(", ")}`);
  }

  const absentLinkResults = [];
  for (const link of spec.absentLinks ?? []) {
    absentLinkResults.push({ link, visible: await visibleRole(page, "link", link) });
  }
  const unexpectedLinks = absentLinkResults.filter((item) => item.visible).map((item) => item.link);
  if (unexpectedLinks.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: unexpected links ${unexpectedLinks.join(", ")}`);
  }

  const absentButtonResults = [];
  for (const button of spec.absentButtons ?? []) {
    absentButtonResults.push({ button, visible: await visibleRole(page, "button", button) });
  }
  const unexpectedButtons = absentButtonResults.filter((item) => item.visible).map((item) => item.button);
  if (unexpectedButtons.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: unexpected buttons ${unexpectedButtons.join(", ")}`);
  }

  const expectedApiResults = [];
  for (const expected of spec.expectedApi ?? []) {
    const match = apiResponses.find((item) => item.url.includes(expected.contains));
    expectedApiResults.push({ ...expected, actualStatus: match?.status ?? null, matchedUrl: match?.url ?? null });
    if (!match || match.status !== expected.status) {
      throw new Error(
        `${spec.role} ${spec.path}: expected API ${expected.contains} ${expected.status}, got ${match?.status ?? "missing"}`,
      );
    }
  }

  const expectedErrorStatuses = new Set(
    (spec.expectedApi ?? []).filter((item) => item.status >= 400).map((item) => item.status),
  );
  const unexpectedConsoleMessages = consoleMessages.filter((message) => {
    if (!message.text.includes("Failed to load resource: the server responded with a status of")) {
      return true;
    }
    return ![...expectedErrorStatuses].some((status) => message.text.includes(`status of ${status}`));
  });
  if (unexpectedConsoleMessages.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: console messages: ${JSON.stringify(unexpectedConsoleMessages)}`);
  }

  const forbiddenApiHits = (spec.forbiddenApiIncludes ?? []).flatMap((needle) =>
    apiResponses.filter((item) => item.url.includes(needle)).map((item) => ({ needle, ...item })),
  );
  if (forbiddenApiHits.length > 0) {
    throw new Error(`${spec.role} ${spec.path}: forbidden API calls ${JSON.stringify(forbiddenApiHits)}`);
  }

  await context.close();
  return {
    role: spec.role,
    path: spec.path,
    url: routeUrl,
    bodySnippet: bodyText.slice(0, 240),
    headings: headingResults,
    presentLinks: presentLinkResults,
    absentLinks: absentLinkResults,
    absentButtons: absentButtonResults,
    expectedApi: expectedApiResults,
    forbiddenApiHits,
    consoleMessages,
    screenshot: screenshotPath,
  };
}

async function probeDirectApi(spec) {
  const token = assertToken(spec.role);
  const response = await fetch(`${apiOrigin}${spec.path}`, {
    method: spec.method,
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      ...(spec.payload ? { "Content-Type": "application/json" } : {}),
    },
    body: spec.payload ? JSON.stringify(spec.payload) : undefined,
  });
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : null;
  if (response.status !== spec.expectedStatus) {
    throw new Error(`${spec.role} ${spec.method} ${spec.path}: expected ${spec.expectedStatus}, got ${response.status}`);
  }
  if (spec.expectedDetail !== undefined && detail !== spec.expectedDetail) {
    throw new Error(
      `${spec.role} ${spec.method} ${spec.path}: expected detail ${spec.expectedDetail}, got ${JSON.stringify(detail)}`,
    );
  }
  return {
    role: spec.role,
    method: spec.method,
    path: spec.path,
    status: response.status,
    detail,
    payload,
  };
}

mkdirSync(screenshotDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  const results = [];
  for (const spec of scenarios) {
    results.push(await probeScenario(browser, spec));
  }
  const directApiResults = [];
  for (const spec of directApiChecks) {
    directApiResults.push(await probeDirectApi(spec));
  }
  const payload = {
    checked_at: new Date().toISOString(),
    admin_base_url: adminBaseUrl,
    api_origin: apiOrigin,
    results,
    directApiResults,
  };
  writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(payload, null, 2));
} finally {
  await browser.close();
}

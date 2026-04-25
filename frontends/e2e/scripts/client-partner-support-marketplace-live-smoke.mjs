import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../../..");
const screenshotDir = resolve(repoRoot, "docs/diag/screenshots");
const outputPath = process.env.CLIENT_PARTNER_SUPPORT_SMOKE_OUTPUT
  ? resolve(process.cwd(), process.env.CLIENT_PARTNER_SUPPORT_SMOKE_OUTPUT)
  : resolve(repoRoot, "docs/diag/client-partner-support-marketplace-live-smoke.json");

const gatewayBase = (process.env.GATEWAY_BASE_URL ?? "http://localhost").replace(/\/+$/, "");
const clientBaseUrl = (process.env.CLIENT_PORTAL_URL ?? `${gatewayBase}/client`).replace(/\/+$/, "");
const partnerBaseUrl = (process.env.PARTNER_PORTAL_URL ?? `${gatewayBase}/partner`).replace(/\/+$/, "");
const authBaseUrl = (process.env.AUTH_BASE_URL ?? `${gatewayBase}/api/v1/auth`).replace(/\/+$/, "");
const clientEmail = process.env.CLIENT_EMAIL ?? "client@neft.local";
const clientPassword = process.env.CLIENT_PASSWORD ?? "Client123!";
const partnerEmail = process.env.PARTNER_EMAIL ?? "partner@neft.local";
const partnerPassword = process.env.PARTNER_PASSWORD ?? "Partner123!";

const screenshotOptions = { fullPage: true };
const incidentsTabPattern = /Incidents|Инциденты/i;
const supportHeadingPattern = /Support|Поддержка/i;

const allowlistedConsolePatterns = [
  /status of 404/i,
  /consequences/i,
  /status of 409/i,
  /settlement_not_finalized/i,
];

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function capturePageDebug(page, screenshotName) {
  const screenshotPath = resolve(screenshotDir, screenshotName);
  await page.screenshot({ path: screenshotPath, ...screenshotOptions }).catch(() => undefined);

  const [href, heading, buttons, links, text] = await Promise.all([
    page.url(),
    page.locator("h1, h2").first().innerText().catch(() => null),
    page
      .locator("button")
      .evaluateAll((elements) =>
        elements
          .map((element) => element.textContent?.trim())
          .filter((value) => Boolean(value))
          .slice(0, 12),
      )
      .catch(() => []),
    page
      .locator("a")
      .evaluateAll((elements) =>
        elements
          .map((element) => ({
            text: element.textContent?.trim() ?? "",
            href: element.getAttribute("href") ?? "",
          }))
          .filter((item) => item.text || item.href)
          .slice(0, 12),
      )
      .catch(() => []),
    page
      .locator("body")
      .innerText()
      .then((value) => value.replace(/\s+/g, " ").trim().slice(0, 1200))
      .catch(() => ""),
  ]);

  return { screenshotPath, href, heading, buttons, links, text };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}: ${typeof payload === "string" ? payload : JSON.stringify(payload)}`);
  }
  return payload;
}

async function login({ email, password, portal }) {
  const payload = await fetchJson(`${authBaseUrl}/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password, portal }),
  });
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token ?? null,
    expiresIn: Number(payload.expires_in ?? 3600),
    email: payload.email ?? email,
    roles: Array.isArray(payload.roles) ? payload.roles : [],
    subjectType: payload.subject_type ?? null,
    clientId: payload.client_id ?? null,
    partnerId: payload.partner_id ?? null,
  };
}

async function fetchAuthedJson(path, token) {
  return fetchJson(`${gatewayBase}${path}`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });
}

function byNewest(left, right) {
  const leftTime = Date.parse(left.updated_at ?? left.created_at ?? 0) || 0;
  const rightTime = Date.parse(right.updated_at ?? right.created_at ?? 0) || 0;
  return rightTime - leftTime;
}

async function discoverIncidentRuntime(clientSession, partnerSession) {
  const partnerOrders = await fetchAuthedJson("/api/core/v1/marketplace/partner/orders", partnerSession.accessToken);
  const candidates = [...(partnerOrders.items ?? [])].sort(byNewest);

  for (const candidate of candidates) {
    const orderId = String(candidate.id ?? "");
    if (!orderId) {
      continue;
    }
    const partnerIncidents = await fetchAuthedJson(
      `/api/core/v1/marketplace/partner/orders/${orderId}/incidents`,
      partnerSession.accessToken,
    );
    const clientIncidents = await fetchAuthedJson(
      `/api/core/v1/marketplace/client/orders/${orderId}/incidents`,
      clientSession.accessToken,
    );
    const partnerCase = partnerIncidents.items?.[0] ?? null;
    const clientCase = clientIncidents.items?.[0] ?? null;
    if (!partnerCase || !clientCase) {
      continue;
    }
    if (String(partnerCase.id ?? "") !== String(clientCase.id ?? "")) {
      continue;
    }

    const caseId = String(partnerCase.id ?? "");
    const clientCaseDetail = await fetchAuthedJson(`/api/core/cases/${caseId}`, clientSession.accessToken);
    const partnerCaseDetail = await fetchAuthedJson(`/api/core/cases/${caseId}`, partnerSession.accessToken);

    return {
      orderId,
      caseId,
      caseTitle: String(partnerCase.title ?? clientCase.title ?? ""),
      caseStatus: String(partnerCase.status ?? clientCase.status ?? ""),
      sourceRefType: partnerCase.case_source_ref_type ?? partnerCase.source_ref_type ?? null,
      sourceRefId: partnerCase.case_source_ref_id ?? partnerCase.source_ref_id ?? null,
      clientIncidents,
      partnerIncidents,
      clientCaseDetail,
      partnerCaseDetail,
    };
  }

  throw new Error("Could not find a recent marketplace order with a shared client/partner incident case.");
}

function expectNoUnexpectedConsoleMessages(messages, label) {
  const unexpected = messages.filter(
    (message) => !allowlistedConsolePatterns.some((pattern) => pattern.test(message.text)),
  );
  if (unexpected.length > 0) {
    throw new Error(`${label}: unexpected console messages ${JSON.stringify(unexpected)}`);
  }
}

async function openIncidentsTab(page, screenshotName, label) {
  const incidentsButton = page.getByRole("button", { name: incidentsTabPattern });
  try {
    await incidentsButton.click({ timeout: 30_000 });
  } catch (error) {
    const debug = await capturePageDebug(page, screenshotName);
    throw new Error(
      `${label} did not expose incidents tab: ${error instanceof Error ? error.message : String(error)}; ` +
        `url=${debug.href}; heading=${debug.heading ?? "null"}; buttons=${JSON.stringify(debug.buttons)}; ` +
        `links=${JSON.stringify(debug.links)}; text=${JSON.stringify(debug.text)}; screenshot=${debug.screenshotPath}`,
    );
  }
}

async function runClientScenario(browser, session, runtime) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 980 } });
  const apiResponses = [];
  const consoleMessages = [];
  const pageErrors = [];
  const navigations = [];
  const failedRequests = [];

  await context.addInitScript((payload) => {
    localStorage.setItem("access_token", payload.accessToken);
    localStorage.setItem("expires_at", String(Date.now() + payload.expiresIn * 1000));
    if (payload.refreshToken) {
      localStorage.setItem("refresh_token", payload.refreshToken);
    } else {
      localStorage.removeItem("refresh_token");
    }
    localStorage.setItem(
      "neft_client_access_token",
      JSON.stringify({
        token: payload.accessToken,
        refreshToken: payload.refreshToken,
        email: payload.email,
        roles: payload.roles,
        subjectType: payload.subjectType,
        clientId: payload.clientId,
        expiresAt: Date.now() + payload.expiresIn * 1000,
      }),
    );
  }, session);

  const page = await context.newPage();
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleMessages.push({ type: message.type(), text: message.text() });
    }
  });
  page.on("pageerror", (error) => {
    pageErrors.push(error.message);
  });
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) {
      navigations.push(frame.url());
    }
  });
  page.on("response", (response) => {
    const url = response.url();
    if (url.includes("/api/")) {
      apiResponses.push({ url, status: response.status() });
    }
  });
  page.on("requestfailed", (request) => {
    failedRequests.push({
      url: request.url(),
      method: request.method(),
      failure: request.failure()?.errorText ?? null,
    });
  });

  const orderUrl = `${clientBaseUrl}/marketplace/orders/${runtime.orderId}`;
  await page.goto(orderUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
  try {
    await openIncidentsTab(page, "client-order-detail-debug.png", "client order detail");
  } catch (error) {
    throw new Error(
      `${error instanceof Error ? error.message : String(error)}; ` +
        `navigations=${JSON.stringify(navigations)}; ` +
        `apiResponses=${JSON.stringify(apiResponses.slice(-20))}; ` +
        `failedRequests=${JSON.stringify(failedRequests.slice(-20))}`,
    );
  }
  await page.getByText(runtime.caseTitle, { exact: false }).waitFor({ state: "visible", timeout: 20_000 });

  const caseLink = page.locator(`a[href$="/cases/${runtime.caseId}"]`).first();
  const caseHref = await caseLink.getAttribute("href");
  assert(caseHref, "client order incidents did not expose a case link");
  assert(caseHref.endsWith(`/cases/${runtime.caseId}`), `unexpected client case href ${caseHref}`);

  const clientIncidentsScreenshot = resolve(screenshotDir, "client-marketplace-order-incidents.png");
  await page.screenshot({ path: clientIncidentsScreenshot, ...screenshotOptions });

  await caseLink.click();
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
  await page.getByText(runtime.caseTitle, { exact: false }).waitFor({ state: "visible", timeout: 20_000 });
  await page.getByText(`${runtime.sourceRefType} / ${runtime.sourceRefId}`, { exact: false }).waitFor({
    state: "visible",
    timeout: 20_000,
  });

  const supportNav = page.locator('a[href$="/support"]').first();
  const supportNavHref = await supportNav.getAttribute("href");
  const supportNavClass = (await supportNav.getAttribute("class")) ?? "";
  assert(supportNavHref, "client support nav link is missing");
  assert(supportNavClass.includes("neftc-nav-item--active"), "client support nav is not active on canonical case trail");

  const clientCaseScreenshot = resolve(screenshotDir, "client-case-detail-support-trail.png");
  await page.screenshot({ path: clientCaseScreenshot, ...screenshotOptions });

  await supportNav.click();
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
  await page.getByRole("heading", { name: supportHeadingPattern }).waitFor({ state: "visible", timeout: 20_000 });

  const clientSupportScreenshot = resolve(screenshotDir, "client-support-inbox.png");
  await page.screenshot({ path: clientSupportScreenshot, ...screenshotOptions });

  assert(pageErrors.length === 0, `client scenario page errors: ${pageErrors.join(" | ")}`);
  expectNoUnexpectedConsoleMessages(consoleMessages, "client scenario");

  await context.close();
  return {
    orderUrl,
    caseHref,
    supportHref: supportNavHref,
    expectedApi: [
      {
        contains: `/api/core/v1/marketplace/client/orders/${runtime.orderId}/incidents`,
        status: apiResponses.find((item) =>
          item.url.includes(`/api/core/v1/marketplace/client/orders/${runtime.orderId}/incidents`),
        )
          ?.status ?? null,
      },
      {
        contains: `/api/core/cases/${runtime.caseId}`,
        status: apiResponses.find((item) => item.url.includes(`/api/core/cases/${runtime.caseId}`))?.status ?? null,
      },
      {
        contains: "/api/core/client/support/tickets",
        status: apiResponses.find((item) => item.url.includes("/api/core/client/support/tickets"))?.status ?? null,
      },
    ],
    screenshots: [clientIncidentsScreenshot, clientCaseScreenshot, clientSupportScreenshot],
    consoleMessages,
  };
}

async function runPartnerScenario(browser, session, runtime) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 980 } });
  const apiResponses = [];
  const consoleMessages = [];
  const pageErrors = [];
  const navigations = [];
  const failedRequests = [];

  await context.addInitScript((payload) => {
    localStorage.setItem(
      "neft_partner_access_token",
      JSON.stringify({
        token: payload.accessToken,
        email: payload.email,
        roles: payload.roles,
        subjectType: payload.subjectType,
        partnerId: payload.partnerId,
        expiresAt: Date.now() + payload.expiresIn * 1000,
      }),
    );
  }, session);

  const page = await context.newPage();
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleMessages.push({ type: message.type(), text: message.text() });
    }
  });
  page.on("pageerror", (error) => {
    pageErrors.push(error.message);
  });
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) {
      navigations.push(frame.url());
    }
  });
  page.on("response", (response) => {
    const url = response.url();
    if (url.includes("/api/")) {
      apiResponses.push({ url, status: response.status() });
    }
  });
  page.on("requestfailed", (request) => {
    failedRequests.push({
      url: request.url(),
      method: request.method(),
      failure: request.failure()?.errorText ?? null,
    });
  });

  const orderUrl = `${partnerBaseUrl}/orders/${runtime.orderId}`;
  await page.goto(orderUrl, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
  try {
    await openIncidentsTab(page, "partner-order-detail-debug.png", "partner order detail");
  } catch (error) {
    throw new Error(
      `${error instanceof Error ? error.message : String(error)}; ` +
        `navigations=${JSON.stringify(navigations)}; ` +
        `apiResponses=${JSON.stringify(apiResponses.slice(-20))}; ` +
        `failedRequests=${JSON.stringify(failedRequests.slice(-20))}`,
    );
  }
  await page.getByText(runtime.caseTitle, { exact: false }).waitFor({ state: "visible", timeout: 20_000 });
  await page.getByText(`${runtime.sourceRefType} / ${runtime.sourceRefId}`, { exact: false }).waitFor({
    state: "visible",
    timeout: 20_000,
  });

  const caseLink = page.locator(`a[href$="/cases/${runtime.caseId}"]`).first();
  const caseHref = await caseLink.getAttribute("href");
  assert(caseHref, "partner order incidents did not expose a case link");
  assert(caseHref.endsWith(`/cases/${runtime.caseId}`), `unexpected partner case href ${caseHref}`);

  const partnerIncidentsScreenshot = resolve(screenshotDir, "partner-marketplace-order-incidents.png");
  await page.screenshot({ path: partnerIncidentsScreenshot, ...screenshotOptions });

  await caseLink.click();
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
  await page.getByText(runtime.caseTitle, { exact: false }).waitFor({ state: "visible", timeout: 20_000 });

  const backLink = page.locator('main a[href$="/support/requests"]').first();
  const backHref = await backLink.getAttribute("href");
  assert(backHref, "partner case detail did not expose back-to-support link");

  const supportNav = page.locator('aside a[href$="/support/requests"]').first();
  const supportNavHref = await supportNav.getAttribute("href");
  const supportNavCurrent = await supportNav.getAttribute("aria-current");
  assert(supportNavHref, "partner support nav link is missing");
  assert(supportNavCurrent === "page", "partner support nav is not active on canonical case trail");

  const partnerCaseScreenshot = resolve(screenshotDir, "partner-case-detail-support-trail.png");
  await page.screenshot({ path: partnerCaseScreenshot, ...screenshotOptions });

  await supportNav.click();
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => undefined);
  const partnerHeading = await page.locator("h1").first().innerText();
  assert(Boolean(partnerHeading.trim()), "partner support page did not render a heading");

  const partnerSupportScreenshot = resolve(screenshotDir, "partner-support-inbox.png");
  await page.screenshot({ path: partnerSupportScreenshot, ...screenshotOptions });

  assert(pageErrors.length === 0, `partner scenario page errors: ${pageErrors.join(" | ")}`);
  expectNoUnexpectedConsoleMessages(consoleMessages, "partner scenario");

  await context.close();
  return {
    orderUrl,
    caseHref,
    supportHref: supportNavHref,
    backHref,
    partnerHeading,
    expectedApi: [
      {
        contains: `/api/core/v1/marketplace/partner/orders/${runtime.orderId}/incidents`,
        status: apiResponses.find((item) =>
          item.url.includes(`/api/core/v1/marketplace/partner/orders/${runtime.orderId}/incidents`),
        )
          ?.status ?? null,
      },
      {
        contains: `/api/core/cases/${runtime.caseId}`,
        status: apiResponses.find((item) => item.url.includes(`/api/core/cases/${runtime.caseId}`))?.status ?? null,
      },
      {
        contains: "/api/core/cases?",
        status: apiResponses.find((item) => item.url.includes("/api/core/cases?"))?.status ?? null,
      },
    ],
    screenshots: [partnerIncidentsScreenshot, partnerCaseScreenshot, partnerSupportScreenshot],
    consoleMessages,
  };
}

mkdirSync(screenshotDir, { recursive: true });

const clientSession = await login({ email: clientEmail, password: clientPassword, portal: "client" });
const partnerSession = await login({ email: partnerEmail, password: partnerPassword, portal: "partner" });
const runtime = await discoverIncidentRuntime(clientSession, partnerSession);

const browser = await chromium.launch({ headless: true });
try {
  const clientResult = await runClientScenario(browser, clientSession, runtime);
  const partnerResult = await runPartnerScenario(browser, partnerSession, runtime);

  const payload = {
    checked_at: new Date().toISOString(),
    gateway_base_url: gatewayBase,
    client_portal_url: clientBaseUrl,
    partner_portal_url: partnerBaseUrl,
    order_id: runtime.orderId,
    case_id: runtime.caseId,
    case_title: runtime.caseTitle,
    source_ref_type: runtime.sourceRefType,
    source_ref_id: runtime.sourceRefId,
    direct_api: {
      client_incidents_total: runtime.clientIncidents.total ?? runtime.clientIncidents.items?.length ?? 0,
      partner_incidents_total: runtime.partnerIncidents.total ?? runtime.partnerIncidents.items?.length ?? 0,
      client_case_status: runtime.clientCaseDetail.case?.status ?? null,
      partner_case_status: runtime.partnerCaseDetail.case?.status ?? null,
    },
    client: clientResult,
    partner: partnerResult,
  };

  writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(payload, null, 2));
} finally {
  await browser.close();
}

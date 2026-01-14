import fs from "node:fs";
import path from "node:path";
import type { ConsoleMessage, Page } from "@playwright/test";
import { detectLoginState, loginViaUi } from "../utils";

type AppName = "admin" | "client" | "partner";

type Credentials = {
  email: string;
  password: string;
};

type RouteConfig = {
  id: string;
  path: string;
  label: string;
  details?: boolean;
};

type FailureStatus =
  | "FAIL_REDIRECT_LOGIN"
  | "FAIL_NOT_FOUND"
  | "FAIL_JS_ERROR"
  | "FAIL_RBAC_DENY"
  | "FAIL_APP_SHELL_MISSING"
  | "FAIL_NAV_ERROR"
  | "FAIL_LOGIN_SERVICE_DOWN"
  | `FAIL_HTTP_${number}`;

type RouteResult = {
  id: string;
  path: string;
  label: string;
  status: "OK" | FailureStatus;
  screenshot?: string;
  detailsScreenshot?: string;
  emptyStateScreenshot?: string;
  note?: string;
};

type ReportState = {
  runId: string;
  baseUrls: Record<AppName, string>;
  routes: Record<AppName, RouteResult[]>;
  screenshots: string[];
  errors: string[];
};

let cachedRunId: string | null = null;

function formatRunId(date: Date) {
  const pad = (value: number) => value.toString().padStart(2, "0");
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join("-") + `_${pad(date.getHours())}${pad(date.getMinutes())}`;
}

export function getRunId() {
  if (!cachedRunId) {
    cachedRunId = process.env.UI_SNAPSHOT_RUN_ID || formatRunId(new Date());
  }
  return cachedRunId;
}

export function getOutputRoot() {
  return path.join(process.cwd(), "ui-audit", getRunId());
}

function ensureDir(dirPath: string) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function normalizeBaseUrl(url: string) {
  return url.endsWith("/") ? url : `${url}/`;
}

function normalizeCredential(value: string | undefined, fallback: string) {
  if (value && value.trim() !== "") {
    return value;
  }
  return fallback;
}

async function isVisible(locator: ReturnType<Page["locator"]>) {
  return (await locator.count()) > 0 && (await locator.first().isVisible());
}

async function isAppShellVisible(page: Page) {
  const sidebar = page.locator(".brand-sidebar, .sidebar, [role='navigation']");
  const header = page.locator(".brand-header, .topbar, header");
  const logoutButton = page.getByRole("button", { name: /выход|logout/i });
  return (await isVisible(sidebar)) && (await isVisible(header)) && (await isVisible(logoutButton));
}

export function resolveBaseUrls() {
  const base = normalizeBaseUrl(process.env.E2E_BASE_URL || "http://localhost");
  return {
    admin: normalizeBaseUrl(process.env.E2E_ADMIN_URL || `${base}admin/`),
    client: normalizeBaseUrl(process.env.E2E_CLIENT_URL || `${base}client/`),
    partner: normalizeBaseUrl(process.env.E2E_PARTNER_URL || `${base}partner/`),
  } satisfies Record<AppName, string>;
}

export function createReportState(baseUrls: Record<AppName, string>): ReportState {
  return {
    runId: getRunId(),
    baseUrls,
    routes: {
      admin: [],
      client: [],
      partner: [],
    },
    screenshots: [],
    errors: [],
  };
}

function buildUrl(baseUrl: string, routePath: string) {
  const normalizedPath = routePath.replace(/^\//, "");
  return new URL(normalizedPath, normalizeBaseUrl(baseUrl)).toString();
}

type NavigationSignals = {
  pageErrors: string[];
  responseStatuses: number[];
};

type NavigationTracker = {
  start: () => void;
  stop: () => NavigationSignals;
};

function createNavigationTracker(page: Page): NavigationTracker {
  let pageErrors: string[] = [];
  let responseStatuses: number[] = [];
  let tracking = false;

  page.on("pageerror", (error) => {
    if (tracking) {
      pageErrors.push(error.message);
    }
  });

  page.on("response", (response) => {
    if (!tracking) {
      return;
    }
    responseStatuses.push(response.status());
  });

  return {
    start: () => {
      pageErrors = [];
      responseStatuses = [];
      tracking = true;
    },
    stop: () => {
      tracking = false;
      return { pageErrors, responseStatuses };
    },
  };
}

async function hasVisibleText(page: Page, text: string) {
  const locator = page.getByText(text, { exact: false });
  const count = await locator.count();
  for (let index = 0; index < count; index += 1) {
    if (await locator.nth(index).isVisible()) {
      return true;
    }
  }
  return false;
}

async function hasAppShell(page: Page) {
  const locator = page.locator(
    "nav, aside, [data-testid='app-shell'], [data-testid='user-menu'], [data-testid='profile-menu'], header, [data-testid='header'], [data-testid='topbar'], button:has-text('Выйти'), a:has-text('Выйти')",
  );
  const count = await locator.count();
  for (let index = 0; index < count; index += 1) {
    if (await locator.nth(index).isVisible()) {
      return true;
    }
  }
  return false;
}

async function getFailureReason({
  page,
  responseStatus,
  signals,
}: {
  page: Page;
  responseStatus?: number;
  signals?: NavigationSignals;
}): Promise<FailureStatus | null> {
  const loginState = await detectLoginState(page);
  if (loginState === "LOGIN_SERVICE_DOWN") {
    return "FAIL_LOGIN_SERVICE_DOWN";
  }
  if (loginState === "LOGIN_READY" && !(await hasAppShell(page))) {
    return "FAIL_REDIRECT_LOGIN";
  }

  if (await hasVisibleText(page, "Страница не найдена")) {
    return "FAIL_NOT_FOUND";
  }

  if (responseStatus === 404 || signals?.responseStatuses.includes(404)) {
    return "FAIL_NOT_FOUND";
  }

  if (responseStatus === 403 || signals?.responseStatuses.includes(403)) {
    return "FAIL_RBAC_DENY";
  }

  if (signals?.pageErrors.length) {
    return "FAIL_JS_ERROR";
  }

  if (!(await hasAppShell(page))) {
    return "FAIL_APP_SHELL_MISSING";
  }

  if (responseStatus && responseStatus >= 400) {
    return `FAIL_HTTP_${responseStatus}`;
  }

  const errorStatus = signals?.responseStatuses.find((status) => status >= 400);
  if (errorStatus) {
    return `FAIL_HTTP_${errorStatus}`;
  }

  return null;
}

export async function login(
  page: Page,
  baseUrl: string,
  credentials: Credentials,
  report: ReportState,
  app: AppName,
  tracker: NavigationTracker,
) {
  try {
    tracker.start();
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(300);

    const authUrl = process.env.ADMIN_AUTH_URL ?? "http://localhost/api/auth/v1/auth/login";
    const loginState = await loginViaUi({
      page,
      baseUrl,
      emailValue: credentials.email,
      passwordValue: credentials.password,
    });
    tracker.stop();

    if (loginState === "ALREADY_AUTHENTICATED") {
      return true;
    }
    if (loginState === "LOGIN_INPUTS_NOT_FOUND") {
      const screenshot = await takeScreenshot(page, report, app, "login__LOGIN_INPUTS_NOT_FOUND");
      report.errors.push(
        `[${app}] login page validation failed: LOGIN_INPUTS_NOT_FOUND (auth: ${authUrl}) (${screenshot})`,
      );
      return false;
    }
    if (loginState === "LOGIN_SERVICE_DOWN") {
      const screenshot = await takeScreenshot(page, report, app, "login__LOGIN_SERVICE_DOWN");
      report.errors.push(
        `[${app}] login page validation failed: LOGIN_SERVICE_DOWN (auth: ${authUrl}) (${screenshot})`,
      );
      return false;
    }

    const screenshot = await takeScreenshot(page, report, app, "login__FAIL_REDIRECT_LOGIN");
    report.errors.push(`[${app}] login validation failed: FAIL_REDIRECT_LOGIN (auth: ${authUrl}) (${screenshot})`);
    return false;
  } catch (error) {
    tracker.stop();
    const authUrl = process.env.ADMIN_AUTH_URL ?? "http://localhost/api/auth/v1/auth/login";
    report.errors.push(`[${app}] login failed: ${(error as Error).message} (auth: ${authUrl})`);
    const screenshot = await takeScreenshot(page, report, app, "login__FAIL_EXCEPTION");
    report.errors.push(`[${app}] login screenshot: ${screenshot}`);
    return false;
  }
}

async function takeScreenshot(page: Page, report: ReportState, app: AppName, fileName: string) {
  const outputRoot = getOutputRoot();
  const appDir = path.join(outputRoot, app);
  ensureDir(appDir);
  const filePath = path.join(appDir, `${fileName}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  const relativePath = path.join(app, `${fileName}.png`);
  report.screenshots.push(relativePath);
  return relativePath;
}

async function visitAndSnap({
  page,
  app,
  report,
  route,
  url,
  responseStatus,
  signals,
  jsErrors,
  consoleErrors,
}: {
  page: Page;
  app: AppName;
  report: ReportState;
  route: RouteConfig;
  url: string;
  responseStatus?: number;
  signals?: NavigationSignals;
  jsErrors: string[];
  consoleErrors: string[];
}) {
  const failureReason = await getFailureReason({ page, responseStatus, signals });
  if (failureReason) {
    const failScreenshot = await takeScreenshot(page, report, app, `${route.id}__${failureReason}`);
    report.errors.push(`[${app}] ${route.label}: ${failureReason} (${url})`);
    if (failureReason === "FAIL_JS_ERROR" && jsErrors.length > 0) {
      report.errors.push(`[${app}] ${route.label}: js errors: ${jsErrors.join(" | ")}`);
    }
    if (failureReason === "FAIL_JS_ERROR" && consoleErrors.length > 0) {
      report.errors.push(`[${app}] ${route.label}: console errors: ${consoleErrors.join(" | ")}`);
    }
    return {
      status: failureReason,
      screenshot: failScreenshot,
    };
  }

  const screenshot = await takeScreenshot(page, report, app, route.id);
  return {
    status: "OK" as const,
    screenshot,
  };
}

async function findFirstRow(page: Page) {
  const tableRows = page.locator("table tbody tr");
  if ((await tableRows.count()) > 0) {
    return tableRows.first();
  }

  const roleRows = page.locator("[role='row']").filter({ has: page.locator("[role='cell']") });
  if ((await roleRows.count()) > 0) {
    return roleRows.first();
  }

  const listRows = page.locator(".table-row, .list-row, .list-item, [data-row]");
  if ((await listRows.count()) > 0) {
    return listRows.first();
  }

  return null;
}

async function tryCaptureDetails(
  page: Page,
  report: ReportState,
  app: AppName,
  route: RouteConfig,
) {
  try {
    const firstRow = await findFirstRow(page);
    if (!firstRow) {
      const emptyStateScreenshot = await takeScreenshot(page, report, app, `${route.id}__empty_state`);
      report.errors.push(`[${app}] ${route.label}: empty state, details not available.`);
      return { emptyStateScreenshot };
    }

    await firstRow.click();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(800);
    const detailsScreenshot = await takeScreenshot(page, report, app, `${route.id}__details`);
    return { detailsScreenshot };
  } catch (error) {
    report.errors.push(`[${app}] ${route.label}: details capture failed: ${(error as Error).message}`);
    return {};
  }
}

export async function runSnapshots({
  page,
  app,
  baseUrl,
  credentials,
  routes,
  report,
}: {
  page: Page;
  app: AppName;
  baseUrl: string;
  credentials: Credentials;
  routes: RouteConfig[];
  report: ReportState;
}) {
  const tracker = createNavigationTracker(page);
  const jsErrors: string[] = [];
  const consoleErrors: string[] = [];
  const onConsole = (msg: ConsoleMessage) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  };

  const onPageError = (err: Error) => {
    jsErrors.push(String(err));
  };

  page.on("console", onConsole);
  page.on("pageerror", onPageError);

  try {
    const loggedIn = await login(page, baseUrl, credentials, report, app, tracker);
    if (!loggedIn) {
      return;
    }

    for (const route of routes) {
      const url = buildUrl(baseUrl, route.path);
      const routeResult: RouteResult = {
        id: route.id,
        path: route.path,
        label: route.label,
        status: "OK",
      };

      jsErrors.length = 0;
      consoleErrors.length = 0;

      try {
        tracker.start();
        const response = await page.goto(url, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(400);
        const signals = tracker.stop();

        const statusCode = response?.status();
        const snapResult = await visitAndSnap({
          page,
          app,
          report,
          route,
          url,
          responseStatus: statusCode,
          signals,
          jsErrors,
          consoleErrors,
        });
        routeResult.status = snapResult.status;
        routeResult.screenshot = snapResult.screenshot;
        if (snapResult.status !== "OK") {
          report.routes[app].push(routeResult);
          continue;
        }

        if (route.details) {
          const { detailsScreenshot, emptyStateScreenshot } = await tryCaptureDetails(page, report, app, route);
          routeResult.detailsScreenshot = detailsScreenshot;
          routeResult.emptyStateScreenshot = emptyStateScreenshot;
        }
      } catch (error) {
        tracker.stop();
        routeResult.status = "FAIL_NAV_ERROR";
        routeResult.screenshot = await takeScreenshot(page, report, app, `${route.id}__FAIL_NAV_ERROR`);
        routeResult.note = (error as Error).message;
        report.errors.push(`[${app}] ${route.label}: navigation failed: ${(error as Error).message}`);
      }

      report.routes[app].push(routeResult);
    }
  } finally {
    page.off("console", onConsole);
    page.off("pageerror", onPageError);
  }
}

export function writeReport(report: ReportState) {
  const outputRoot = getOutputRoot();
  ensureDir(outputRoot);
  const reportPath = path.join(outputRoot, "REPORT.md");

  const lines: string[] = [];
  lines.push(`# UI Snapshot Report`);
  lines.push("");
  lines.push(`Run: ${report.runId}`);
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push("");
  lines.push("## Base URLs");
  lines.push(`- Admin: ${report.baseUrls.admin}`);
  lines.push(`- Client: ${report.baseUrls.client}`);
  lines.push(`- Partner: ${report.baseUrls.partner}`);
  lines.push("");
  lines.push("## Routes");

  const pushRoutes = (app: AppName) => {
    lines.push("");
    lines.push(`### ${app}`);
    for (const route of report.routes[app]) {
      const statusLine = `- ${route.id} (${route.path}) — ${route.status}`;
      lines.push(route.note ? `${statusLine} (${route.note})` : statusLine);
      if (route.screenshot) {
        lines.push(`  - snapshot: ${route.screenshot}`);
      }
      if (route.detailsScreenshot) {
        lines.push(`  - details: ${route.detailsScreenshot}`);
      }
      if (route.emptyStateScreenshot) {
        lines.push(`  - empty state: ${route.emptyStateScreenshot}`);
      }
    }
  };

  pushRoutes("admin");
  pushRoutes("client");
  pushRoutes("partner");

  lines.push("");
  lines.push("## Screenshots");
  if (report.screenshots.length === 0) {
    lines.push("- (none)");
  } else {
    for (const screenshot of report.screenshots) {
      lines.push(`- ${screenshot}`);
    }
  }

  lines.push("");
  lines.push("## Errors");
  if (report.errors.length === 0) {
    lines.push("- (none)");
  } else {
    for (const error of report.errors) {
      lines.push(`- ${error}`);
    }
  }

  fs.writeFileSync(reportPath, lines.join("\n"));
  console.log(`UI audit saved to: ui-audit/${report.runId}`);
  return reportPath;
}

export const ADMIN_ROUTES: RouteConfig[] = [
  { id: "000_dashboard", path: "/", label: "Dashboard" },
  { id: "010_operations", path: "/operations", label: "Operations" },
  { id: "020_transactions", path: "/transactions", label: "Transactions", details: true },
  { id: "030_rules", path: "/rules", label: "Rules" },
  { id: "040_prices", path: "/prices", label: "Prices" },
  { id: "050_billing", path: "/billing", label: "Billing" },
  { id: "060_docs", path: "/docs", label: "Docs" },
  { id: "070_settings", path: "/settings", label: "Settings" },
];

export const CLIENT_ROUTES: RouteConfig[] = [
  { id: "000_home", path: "/", label: "Home" },
  { id: "010_cards", path: "/cards", label: "Cards" },
  { id: "020_limits", path: "/limits", label: "Limits" },
  { id: "030_reports", path: "/reports", label: "Reports", details: true },
  { id: "040_billing", path: "/billing", label: "Billing" },
  { id: "050_support", path: "/support", label: "Support" },
  { id: "060_settings", path: "/settings", label: "Settings" },
];

export const PARTNER_ROUTES: RouteConfig[] = [
  { id: "000_dashboard", path: "/", label: "Dashboard" },
  { id: "010_prices", path: "/prices", label: "Prices" },
  { id: "020_pos", path: "/pos", label: "POS" },
  { id: "030_transactions", path: "/transactions", label: "Transactions", details: true },
  { id: "040_reconciliation", path: "/reconciliation", label: "Reconciliation" },
  { id: "050_billing", path: "/billing", label: "Billing" },
  { id: "060_support", path: "/support", label: "Support" },
  { id: "070_settings", path: "/settings", label: "Settings" },
];

export const CREDENTIALS = {
  admin: {
    email: normalizeCredential(process.env.NEFT_BOOTSTRAP_ADMIN_EMAIL, process.env.ADMIN_EMAIL || "admin@example.com"),
    password: normalizeCredential(process.env.NEFT_BOOTSTRAP_ADMIN_PASSWORD, process.env.ADMIN_PASSWORD || "admin"),
  },
  client: {
    email: normalizeCredential(process.env.NEFT_BOOTSTRAP_CLIENT_EMAIL, process.env.CLIENT_EMAIL || "client@neft.local"),
    password: normalizeCredential(
      process.env.NEFT_BOOTSTRAP_CLIENT_PASSWORD,
      process.env.CLIENT_PASSWORD || "client",
    ),
  },
  partner: {
    email: normalizeCredential(
      process.env.NEFT_BOOTSTRAP_PARTNER_EMAIL,
      process.env.PARTNER_EMAIL || "partner@neft.local",
    ),
    password: normalizeCredential(
      process.env.NEFT_BOOTSTRAP_PARTNER_PASSWORD,
      process.env.PARTNER_PASSWORD || "partner",
    ),
  },
} satisfies Record<AppName, Credentials>;

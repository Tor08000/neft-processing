import fs from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";

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

type RouteResult = {
  id: string;
  path: string;
  label: string;
  status: "OK" | `FAIL (${string})`;
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

export async function login(
  page: Page,
  baseUrl: string,
  credentials: Credentials,
  report: ReportState,
  app: AppName,
  jsErrors: string[],
) {
  try {
    jsErrors.length = 0;
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(300);

    const emailInput = page.locator(
      'input[type="email"], input[name="email"], input[placeholder*="mail" i], input[autocomplete="username"]',
    );
    const passInput = page.locator(
      'input[type="password"], input[name="password"], input[placeholder*="password" i], input[autocomplete="current-password"]',
    );
    const submitButton = page.locator(
      'button[type="submit"], button:has-text("Sign in"), button:has-text("Login"), button:has-text("Войти")',
    );

    if ((await emailInput.count()) === 0 || (await passInput.count()) === 0) {
      report.errors.push(`[${app}] login form not found at ${page.url()}`);
      const screenshot = await takeScreenshot(page, report, app, "login__FAIL_FORM_MISSING");
      report.errors.push(`[${app}] login screenshot: ${screenshot}`);
      return false;
    }

    await emailInput.first().fill(credentials.email);
    await passInput.first().fill(credentials.password);
    await submitButton.first().click();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(300);
    const failureReason = await getFailureReason({ page, jsErrors, requireShell: true });
    if (failureReason) {
      const screenshot = await takeScreenshot(page, report, app, `login__FAIL_${failureReason}`);
      report.errors.push(`[${app}] login failed: ${failureReason} (${page.url()})`);
      report.errors.push(`[${app}] login screenshot: ${screenshot}`);
      return false;
    }
    return true;
  } catch (error) {
    report.errors.push(`[${app}] login failed: ${(error as Error).message}`);
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

async function getFailureReason({
  page,
  responseStatus,
  jsErrors = [],
  requireShell = false,
}: {
  page: Page;
  responseStatus?: number;
  jsErrors?: string[];
  requireShell?: boolean;
}) {
  const currentUrl = page.url();
  if (currentUrl.includes("/login")) {
    return "REDIRECT_LOGIN";
  }

  const notFoundText = page.getByText("Страница не найдена", { exact: false });
  if ((await notFoundText.count()) > 0) {
    return "NOT_FOUND";
  }

  if (responseStatus === 404) {
    return "NOT_FOUND";
  }

  const rbacText = page.getByText("нет прав", { exact: false });
  if (responseStatus === 403 || (await rbacText.count()) > 0) {
    return "RBAC_DENY";
  }

  if (jsErrors.length > 0) {
    return "JS_ERROR";
  }

  if (requireShell && !(await isAppShellVisible(page))) {
    return "APP_SHELL_MISSING";
  }

  if (responseStatus && responseStatus >= 400) {
    return `HTTP_${responseStatus}`;
  }

  return null;
}

async function visitAndSnap({
  page,
  app,
  report,
  route,
  url,
  responseStatus,
  jsErrors,
}: {
  page: Page;
  app: AppName;
  report: ReportState;
  route: RouteConfig;
  url: string;
  responseStatus?: number;
  jsErrors: string[];
}) {
  const failureReason = await getFailureReason({ page, responseStatus, jsErrors, requireShell: true });
  if (failureReason) {
    report.errors.push(`[${app}] ${route.label}: ${failureReason} (${url})`);
    if (failureReason === "JS_ERROR" && jsErrors.length > 0) {
      report.errors.push(`[${app}] ${route.label}: js errors: ${jsErrors.join(" | ")}`);
    }
    const screenshot = await takeScreenshot(page, report, app, `${route.id}__FAIL_${failureReason}`);
    return {
      status: `FAIL (${failureReason})` as const,
      screenshot,
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
  const jsErrors: string[] = [];
  const onConsole = (msg: { type: () => string; text: () => string }) => {
    if (msg.type() === "error") {
      jsErrors.push(`console: ${msg.text()}`);
    }
  };
  const onPageError = (error: Error) => {
    jsErrors.push(`pageerror: ${error.message}`);
  };
  page.on("console", onConsole);
  page.on("pageerror", onPageError);

  await login(page, baseUrl, credentials, report, app, jsErrors);

  for (const route of routes) {
    const url = buildUrl(baseUrl, route.path);
    const routeResult: RouteResult = {
      id: route.id,
      path: route.path,
      label: route.label,
      status: "OK",
    };

    try {
      jsErrors.length = 0;
      const response = await page.goto(url, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(400);

      const statusCode = response?.status();
      const snapResult = await visitAndSnap({
        page,
        app,
        report,
        route,
        url,
        responseStatus: statusCode,
        jsErrors,
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
      routeResult.status = "FAIL (NAV_ERROR)";
      routeResult.note = (error as Error).message;
      report.errors.push(`[${app}] ${route.label}: navigation failed: ${(error as Error).message}`);
    }

    report.routes[app].push(routeResult);
  }

  page.off("console", onConsole);
  page.off("pageerror", onPageError);
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
    password: normalizeCredential(process.env.NEFT_BOOTSTRAP_ADMIN_PASSWORD, process.env.ADMIN_PASSWORD || "admin123"),
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

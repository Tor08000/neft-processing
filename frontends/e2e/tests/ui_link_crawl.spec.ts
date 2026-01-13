import fs from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";
import { test } from "@playwright/test";
import { CREDENTIALS, getRunId, resolveBaseUrls } from "./utils/ui_snapshot";

type AppName = "admin" | "client" | "partner";

type CrawlError = {
  url: string;
  type: string;
  note?: string;
  screenshot?: string;
};

type CrawlState = {
  visited: string[];
  errors: CrawlError[];
};

type CrawlReport = {
  runId: string;
  baseUrls: Record<AppName, string>;
  apps: Record<AppName, CrawlState>;
};

const MAX_VISITED = 200;

function ensureDir(dirPath: string) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function normalizeUrl(url: string) {
  const parsed = new URL(url);
  parsed.hash = "";
  return parsed.toString();
}

function slugifyUrl(url: string) {
  const parsed = new URL(url);
  const raw = `${parsed.pathname}${parsed.search}`;
  const cleaned = raw.replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return cleaned.length > 0 ? cleaned.slice(0, 80) : "home";
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

async function takeScreenshot(page: Page, outputDir: string, fileName: string) {
  ensureDir(outputDir);
  const filePath = path.join(outputDir, `${fileName}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  return filePath;
}

async function login(page: Page, baseUrl: string, email: string, password: string) {
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
    return false;
  }

  await emailInput.first().fill(email);
  await passInput.first().fill(password);
  await submitButton.first().click();
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(300);
  return !page.url().includes("/login") && (await isAppShellVisible(page));
}

async function getFailureReason({
  page,
  responseStatus,
  jsErrors,
  requireShell,
}: {
  page: Page;
  responseStatus?: number;
  jsErrors: string[];
  requireShell: boolean;
}) {
  const currentUrl = page.url();
  if (currentUrl.includes("/login")) {
    return "REDIRECT_LOGIN";
  }

  const notFoundText = page.getByText("Страница не найдена", { exact: false });
  if ((await notFoundText.count()) > 0 || responseStatus === 404) {
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

async function collectLinks(page: Page, baseOrigin: string, basePath: string, currentUrl: string) {
  const rawLinks = await page.$$eval("a[href]", (anchors) =>
    anchors.map((anchor) => anchor.getAttribute("href") || "").filter(Boolean),
  );
  const nextLinks = new Set<string>();
  for (const href of rawLinks) {
    if (href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) {
      continue;
    }
    if (href.startsWith("javascript:")) {
      continue;
    }
    const resolved = new URL(href, currentUrl);
    if (resolved.origin !== baseOrigin) {
      continue;
    }
    if (!resolved.pathname.startsWith(basePath)) {
      continue;
    }
    if (/\/logout|signout/i.test(resolved.pathname)) {
      continue;
    }
    if (/\.(png|jpe?g|svg|gif|webp|ico|css|js|map|json|xml|pdf|zip|csv|xlsx?)$/i.test(resolved.pathname)) {
      continue;
    }
    resolved.hash = "";
    nextLinks.add(resolved.toString());
  }
  return [...nextLinks];
}

async function crawlApp({
  page,
  app,
  baseUrl,
  credentials,
  report,
}: {
  page: Page;
  app: AppName;
  baseUrl: string;
  credentials: { email: string; password: string };
  report: CrawlReport;
}) {
  const runId = getRunId();
  const outputDir = path.join(process.cwd(), "ui-audit", runId, "crawl", app);
  const baseOrigin = new URL(baseUrl).origin;
  const basePath = new URL(baseUrl).pathname.replace(/\/$/, "");

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

  const loggedIn = await login(page, baseUrl, credentials.email, credentials.password);
  if (!loggedIn) {
    const screenshot = await takeScreenshot(page, outputDir, "login__FAIL");
    report.apps[app].errors.push({
      url: page.url(),
      type: "REDIRECT_LOGIN",
      note: "Login failed or app shell missing",
      screenshot,
    });
    page.off("console", onConsole);
    page.off("pageerror", onPageError);
    return;
  }

  const queue: string[] = [normalizeUrl(baseUrl)];
  const visited = new Set<string>();

  while (queue.length > 0 && visited.size < MAX_VISITED) {
    const nextUrl = queue.shift();
    if (!nextUrl || visited.has(nextUrl)) {
      continue;
    }
    visited.add(nextUrl);

    jsErrors.length = 0;
    let responseStatus: number | undefined;
    try {
      const response = await page.goto(nextUrl, { waitUntil: "domcontentloaded" });
      responseStatus = response?.status();
      await page.waitForTimeout(250);
    } catch (error) {
      report.apps[app].errors.push({
        url: nextUrl,
        type: "NAV_ERROR",
        note: (error as Error).message,
      });
      continue;
    }

    const failureReason = await getFailureReason({
      page,
      responseStatus,
      jsErrors,
      requireShell: true,
    });

    if (failureReason) {
      const screenshot = await takeScreenshot(
        page,
        outputDir,
        `${visited.size.toString().padStart(3, "0")}_${slugifyUrl(nextUrl)}__FAIL_${failureReason}`,
      );
      report.apps[app].errors.push({
        url: page.url(),
        type: failureReason,
        note: jsErrors.length ? jsErrors.join(" | ") : undefined,
        screenshot,
      });
      continue;
    }

    if (jsErrors.length > 0) {
      report.apps[app].errors.push({
        url: page.url(),
        type: "CONSOLE_ERROR",
        note: jsErrors.join(" | "),
      });
    }

    report.apps[app].visited.push(page.url());

    const newLinks = await collectLinks(page, baseOrigin, basePath, page.url());
    for (const link of newLinks) {
      const normalized = normalizeUrl(link);
      if (!visited.has(normalized)) {
        queue.push(normalized);
      }
    }
  }

  page.off("console", onConsole);
  page.off("pageerror", onPageError);
}

function writeReport(report: CrawlReport) {
  const outputRoot = path.join(process.cwd(), "ui-audit", report.runId);
  ensureDir(outputRoot);
  const reportPath = path.join(outputRoot, "LINK_REPORT.md");
  const lines: string[] = [];
  lines.push("# UI Link Crawl Report");
  lines.push("");
  lines.push(`Run: ${report.runId}`);
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push("");
  lines.push("## Base URLs");
  lines.push(`- Admin: ${report.baseUrls.admin}`);
  lines.push(`- Client: ${report.baseUrls.client}`);
  lines.push(`- Partner: ${report.baseUrls.partner}`);
  lines.push("");

  const writeAppSection = (app: AppName) => {
    lines.push(`## ${app}`);
    lines.push("");
    lines.push("### Visited");
    if (report.apps[app].visited.length === 0) {
      lines.push("- (none)");
    } else {
      for (const url of report.apps[app].visited) {
        lines.push(`- ${url}`);
      }
    }
    lines.push("");
    lines.push("### Errors");
    if (report.apps[app].errors.length === 0) {
      lines.push("- (none)");
    } else {
      for (const error of report.apps[app].errors) {
        const detail = error.note ? ` — ${error.note}` : "";
        const screenshot = error.screenshot ? ` (screenshot: ${error.screenshot})` : "";
        lines.push(`- ${error.type}: ${error.url}${detail}${screenshot}`);
      }
    }
    lines.push("");
  };

  writeAppSection("admin");
  writeAppSection("client");
  writeAppSection("partner");

  fs.writeFileSync(reportPath, lines.join("\n"));
  return reportPath;
}

test.describe.serial("UI Link Crawl", () => {
  const baseUrls = resolveBaseUrls();
  const report: CrawlReport = {
    runId: getRunId(),
    baseUrls,
    apps: {
      admin: { visited: [], errors: [] },
      client: { visited: [], errors: [] },
      partner: { visited: [], errors: [] },
    },
  };

  test.afterAll(() => {
    writeReport(report);
  });

  test("Admin link crawl", async ({ page }) => {
    await crawlApp({
      page,
      app: "admin",
      baseUrl: baseUrls.admin,
      credentials: CREDENTIALS.admin,
      report,
    });
  });

  test("Client link crawl", async ({ page }) => {
    await crawlApp({
      page,
      app: "client",
      baseUrl: baseUrls.client,
      credentials: CREDENTIALS.client,
      report,
    });
  });

  test("Partner link crawl", async ({ page }) => {
    await crawlApp({
      page,
      app: "partner",
      baseUrl: baseUrls.partner,
      credentials: CREDENTIALS.partner,
      report,
    });
  });
});

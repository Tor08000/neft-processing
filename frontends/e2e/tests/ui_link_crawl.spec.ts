import fs from "node:fs";
import path from "node:path";
import { test } from "@playwright/test";
import type { Page } from "playwright";
import {
  ADMIN_AUTH_URL,
  ADMIN_BASE_URL,
  CLIENT_BASE_URL,
  PARTNER_BASE_URL,
  LoginState,
  detectLoginState,
  loginViaUi,
  CREDENTIALS,
  getOutputRoot,
  getRunId,
} from "./helpers";

type AppName = "admin" | "client" | "partner";

type CrawlEntry = {
  url: string;
  result: "OK" | "FAIL" | "SKIP";
  reason?: string;
  httpErrors: string[];
  consoleErrors: string[];
  screenshot: string;
};

type CrawlReport = Record<AppName, CrawlEntry[]>;

type CrawlTracker = {
  start: () => void;
  stop: () => {
    consoleErrors: string[];
    responseErrors: string[];
    pageErrors: string[];
    assetHtmlErrors: string[];
  };
};

const MAX_PAGES = Number(process.env.MAX_PAGES ?? 200);
const MAX_DEPTH = Number(process.env.MAX_DEPTH ?? 4);
const CRAWL_TIMEOUT_MS = 5_000;

const RUN_ID = getRunId();
const OUTPUT_ROOT = getOutputRoot();

function ensureDir(dirPath: string) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function slugify(value: string) {
  return value
    .replace(/https?:\/\//g, "")
    .replace(/[^a-z0-9]+/gi, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase()
    .slice(0, 80);
}

function normalizeUrl(rawUrl: string) {
  const parsed = new URL(rawUrl);
  parsed.hash = "";
  return parsed.toString();
}

function isAssetPath(pathname: string) {
  const lower = pathname.toLowerCase();
  if (lower.includes("/assets/") || lower.includes("/brand/")) {
    return true;
  }
  return [".png", ".css", ".js"].some((ext) => lower.endsWith(ext));
}

function isDisallowedHref(href: string) {
  return (
    href.startsWith("mailto:") ||
    href.startsWith("tel:") ||
    href.startsWith("#") ||
    href.startsWith("javascript:")
  );
}

function isWithinApp(url: URL, baseUrl: URL, app: AppName) {
  if (url.origin !== baseUrl.origin) {
    return false;
  }
  const pathname = url.pathname;
  const basePath = baseUrl.pathname.replace(/\/+$/, "") || "/";
  const appPrefix = `/${app}`;
  if (basePath !== "/" && pathname.startsWith(basePath)) {
    return true;
  }
  return pathname.startsWith(appPrefix) || basePath === "/";
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

function createTracker(page: Page): CrawlTracker {
  let consoleErrors: string[] = [];
  let responseErrors: string[] = [];
  let pageErrors: string[] = [];
  let assetHtmlErrors: string[] = [];
  let tracking = false;

  page.on("console", (message) => {
    if (tracking && message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });

  page.on("pageerror", (error) => {
    if (tracking) {
      pageErrors.push(error.message);
      consoleErrors.push(error.message);
    }
  });

  page.on("response", (response) => {
    if (tracking) {
      try {
        const url = new URL(response.url());
        const contentType = response.headers()["content-type"] ?? "";
        if (isAssetPath(url.pathname) && contentType.includes("text/html")) {
          assetHtmlErrors.push(`${contentType} ${response.url()}`);
        }
      } catch {
        // Ignore invalid URLs
      }
    }
    if (tracking && response.status() >= 400) {
      responseErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  return {
    start: () => {
      consoleErrors = [];
      responseErrors = [];
      pageErrors = [];
      assetHtmlErrors = [];
      tracking = true;
    },
    stop: () => {
      tracking = false;
      return { consoleErrors, responseErrors, pageErrors, assetHtmlErrors };
    },
  };
}

async function collectAnchorLinks(page: Page) {
  return page.$$eval("nav a[href], aside a[href], header a[href], main a[href]", (elements) =>
    elements.map((element) => element.getAttribute("href") || "").filter(Boolean),
  );
}

async function collectClickableLinks(page: Page) {
  const clickable = page.locator(
    "nav button, aside button, header button, nav [role='menuitem'], aside [role='menuitem'], header [role='menuitem'], nav [role='button'], aside [role='button'], header [role='button']",
  );
  const count = await clickable.count();
  const discovered: string[] = [];
  const originalUrl = page.url();

  for (let index = 0; index < count; index += 1) {
    const element = clickable.nth(index);
    try {
      await element.click({ timeout: 2000 });
      await page.waitForTimeout(300);
      const newUrl = page.url();
      if (newUrl !== originalUrl) {
        discovered.push(newUrl);
        await page.goto(originalUrl, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(200);
      }
    } catch {
      await page.goto(originalUrl, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(200);
    }
  }

  return discovered;
}

function evaluateResult(
  pageUrl: string,
  responseErrors: string[],
  consoleErrors: string[],
  pageErrors: string[],
  assetHtmlErrors: string[],
  loginState: LoginState,
  notFound: boolean,
) {
  if (loginState === "LOGIN_SERVICE_DOWN") {
    return { result: "FAIL" as const, reason: "LOGIN_SERVICE_DOWN" };
  }
  if (loginState === "LOGIN_INPUTS_NOT_FOUND") {
    return { result: "FAIL" as const, reason: "LOGIN_INPUTS_NOT_FOUND" };
  }
  if (loginState === "LOGIN_BAD_ROUTE") {
    return { result: "FAIL" as const, reason: "LOGIN_BAD_ROUTE" };
  }
  if (loginState === "FAIL_LOGIN_BAD_ENDPOINT") {
    return { result: "FAIL" as const, reason: "FAIL_LOGIN_BAD_ENDPOINT" };
  }
  if (loginState === "FAIL_LOGIN_NOT_COMPLETED") {
    return { result: "FAIL" as const, reason: "FAIL_LOGIN_NOT_COMPLETED" };
  }
  if (loginState === "FAIL_AUTH_URL_DUPLICATED") {
    return { result: "FAIL" as const, reason: "FAIL_AUTH_URL_DUPLICATED" };
  }
  if (loginState === "FAIL_AUTH_TOKEN_NOT_STORED") {
    return { result: "FAIL" as const, reason: "FAIL_AUTH_TOKEN_NOT_STORED" };
  }
  if (loginState === "LOGIN_STUCK_ON_LOGIN") {
    return { result: "FAIL" as const, reason: "FAIL_LOGIN_STUCK_ON_LOGIN" };
  }
  if (loginState === "LOGIN_READY") {
    return { result: "FAIL" as const, reason: "REDIRECT_LOGIN" };
  }
  if (notFound) {
    return { result: "FAIL" as const, reason: "NOT_FOUND" };
  }
  if (assetHtmlErrors.length > 0) {
    return { result: "FAIL" as const, reason: "FAIL_STATIC_ASSET_HTML" };
  }
  if (responseErrors.some((error) => error.startsWith("403 "))) {
    return { result: "FAIL" as const, reason: "RBAC_DENY" };
  }
  if (pageErrors.length > 0) {
    return { result: "FAIL" as const, reason: "JS_ERROR" };
  }
  if (responseErrors.length > 0) {
    return { result: "FAIL" as const, reason: "HTTP_ERROR" };
  }
  if (consoleErrors.length > 0) {
    return { result: "FAIL" as const, reason: "CONSOLE_ERROR" };
  }
  return { result: "OK" as const };
}

async function crawlApp({
  page,
  app,
  baseUrl,
  login,
  report,
}: {
  page: Page;
  app: AppName;
  baseUrl: string;
  login: (page: Page) => Promise<LoginState>;
  report: CrawlReport;
}) {
  const tracker = createTracker(page);
  const base = new URL(baseUrl);
  const queue: Array<{ url: string; depth: number }> = [];
  const visited = new Set<string>();
  let index = 0;

  const loginState = await login(page);
  const loginUrl = baseUrl;
  if (loginState === "LOGIN_SERVICE_DOWN") {
    const screenshotPath = path.join(OUTPUT_ROOT, "crawl", app, `${String(index).padStart(3, "0")}_login_service_down.png`);
    ensureDir(path.join(OUTPUT_ROOT, "crawl", app));
    await page.screenshot({ path: screenshotPath, fullPage: true });
    report[app].push({
      url: loginUrl,
      result: "FAIL",
      reason: `LOGIN_SERVICE_DOWN (auth: ${ADMIN_AUTH_URL})`,
      httpErrors: [],
      consoleErrors: [],
      screenshot: path.relative(process.cwd(), screenshotPath),
    });
    throw new Error(`LOGIN_SERVICE_DOWN (auth: ${ADMIN_AUTH_URL})`);
  }
  if (loginState === "LOGIN_INPUTS_NOT_FOUND") {
    const screenshotPath = path.join(OUTPUT_ROOT, "crawl", app, `${String(index).padStart(3, "0")}_login_inputs_missing.png`);
    ensureDir(path.join(OUTPUT_ROOT, "crawl", app));
    await page.screenshot({ path: screenshotPath, fullPage: true });
    report[app].push({
      url: loginUrl,
      result: "FAIL",
      reason: `LOGIN_INPUTS_NOT_FOUND (auth: ${ADMIN_AUTH_URL})`,
      httpErrors: [],
      consoleErrors: [],
      screenshot: path.relative(process.cwd(), screenshotPath),
    });
    throw new Error(`LOGIN_INPUTS_NOT_FOUND (auth: ${ADMIN_AUTH_URL})`);
  }
  if (loginState !== "ALREADY_AUTHENTICATED" && loginState !== "LOGIN_OK") {
    const screenshotPath = path.join(OUTPUT_ROOT, "crawl", app, `${String(index).padStart(3, "0")}_login_not_confirmed.png`);
    ensureDir(path.join(OUTPUT_ROOT, "crawl", app));
    await page.screenshot({ path: screenshotPath, fullPage: true });
    report[app].push({
      url: loginUrl,
      result: "FAIL",
      reason:
        loginState === "LOGIN_BAD_ROUTE"
          ? `LOGIN_BAD_ROUTE (auth: ${ADMIN_AUTH_URL})`
          : loginState === "FAIL_LOGIN_BAD_ENDPOINT"
            ? `FAIL_LOGIN_BAD_ENDPOINT (auth: ${ADMIN_AUTH_URL})`
          : loginState === "FAIL_LOGIN_NOT_COMPLETED"
            ? `FAIL_LOGIN_NOT_COMPLETED (auth: ${ADMIN_AUTH_URL})`
            : loginState === "FAIL_AUTH_URL_DUPLICATED"
              ? `FAIL_AUTH_URL_DUPLICATED (auth: ${ADMIN_AUTH_URL})`
          : loginState === "FAIL_AUTH_TOKEN_NOT_STORED"
            ? `FAIL_AUTH_TOKEN_NOT_STORED (auth: ${ADMIN_AUTH_URL})`
            : loginState === "LOGIN_STUCK_ON_LOGIN"
              ? `FAIL_LOGIN_STUCK_ON_LOGIN (auth: ${ADMIN_AUTH_URL})`
              : `FAIL_REDIRECT_LOGIN (auth: ${ADMIN_AUTH_URL})`,
      httpErrors: [],
      consoleErrors: [],
      screenshot: path.relative(process.cwd(), screenshotPath),
    });
    throw new Error(`Login failed: ${loginState} (auth: ${ADMIN_AUTH_URL})`);
  }

  queue.push({ url: baseUrl, depth: 0 });

  while (queue.length > 0 && visited.size < MAX_PAGES) {
    const current = queue.shift();
    if (!current) {
      continue;
    }
    if (current.depth > MAX_DEPTH) {
      continue;
    }

    const normalized = normalizeUrl(current.url);
    if (visited.has(normalized)) {
      continue;
    }
    visited.add(normalized);

    tracker.start();
    let navigationError: string | null = null;
    try {
      await page.goto(normalized, { waitUntil: "domcontentloaded", timeout: CRAWL_TIMEOUT_MS });
      await page.waitForTimeout(400);
    } catch (error) {
      navigationError = (error as Error).message;
    }
    const { consoleErrors, responseErrors, pageErrors, assetHtmlErrors } = tracker.stop();

    await page.waitForTimeout(800);
    const pageLoginState = await detectLoginState(page);
    const notFound = await hasVisibleText(page, "Страница не найдена");
    const { result, reason } = evaluateResult(
      page.url(),
      responseErrors,
      consoleErrors,
      pageErrors,
      assetHtmlErrors,
      pageLoginState,
      notFound,
    );

    ensureDir(path.join(OUTPUT_ROOT, "crawl", app));
    const slug = slugify(page.url());
    const screenshotPath = path.join(
      OUTPUT_ROOT,
      "crawl",
      app,
      `${String(index).padStart(3, "0")}_${slug || "page"}.png`,
    );
    await page.screenshot({ path: screenshotPath, fullPage: true });

    report[app].push({
      url: page.url(),
      result: navigationError ? "FAIL" : result,
      reason: navigationError ? "NAV_ERROR" : reason,
      httpErrors: responseErrors,
      consoleErrors,
      screenshot: path.relative(process.cwd(), screenshotPath),
    });

    index += 1;
    if (navigationError) {
      continue;
    }

    const anchorLinks = await collectAnchorLinks(page);
    const clickableLinks = await collectClickableLinks(page);
    const rawLinks = [...anchorLinks, ...clickableLinks];
    for (const href of rawLinks) {
      if (!href || isDisallowedHref(href)) {
        continue;
      }
      const linkUrl = new URL(href, page.url());
      if (isAssetPath(linkUrl.pathname)) {
        continue;
      }
      if (!isWithinApp(linkUrl, base, app)) {
        continue;
      }
      const normalizedLink = normalizeUrl(linkUrl.toString());
      if (!visited.has(normalizedLink)) {
        queue.push({ url: normalizedLink, depth: current.depth + 1 });
      }
    }
  }
}

function writeLinkReport(report: CrawlReport) {
  ensureDir(OUTPUT_ROOT);
  const reportPath = path.join(OUTPUT_ROOT, "LINK_REPORT.md");
  const lines: string[] = [];
  lines.push("# UI Link Crawl Report");
  lines.push("");
  lines.push(`Run: ${RUN_ID}`);
  lines.push(`Generated: ${new Date().toISOString()}`);
  lines.push("");

  (["admin", "client", "partner"] as AppName[]).forEach((app) => {
    lines.push(`## ${app}`);
    lines.push("");
    lines.push("| URL | Result | Reason | HTTP errors | Console errors | Screenshot |");
    lines.push("| --- | ------ | ------ | ----------- | -------------- | ---------- |");
    if (report[app].length === 0) {
      lines.push("| - | FAIL | NO_PAGES_DISCOVERED |  |  |  |");
    } else {
      for (const entry of report[app]) {
        lines.push(
          `| ${entry.url} | ${entry.result} | ${entry.reason ?? ""} | ${entry.httpErrors.join("<br>")} | ${entry.consoleErrors.join("<br>")} | ${entry.screenshot} |`,
        );
      }
    }
    lines.push("");
  });

  fs.writeFileSync(reportPath, lines.join("\n"));
  return reportPath;
}

test.describe.serial("UI Link Crawler", () => {
  const report: CrawlReport = { admin: [], client: [], partner: [] };

  test.afterAll(() => {
    const reportPath = writeLinkReport(report);
    console.log(`UI audit saved to: ui-audit/${RUN_ID}`);
    console.log(`LINK_REPORT: ${reportPath}`);
  });

  test("Admin UI link crawl", async ({ page }) => {
    await crawlApp({
      page,
      app: "admin",
      baseUrl: ADMIN_BASE_URL,
      login: (loginPage) =>
        loginViaUi({
          page: loginPage,
          baseUrl: ADMIN_BASE_URL,
          emailValue: CREDENTIALS.admin.email,
          passwordValue: CREDENTIALS.admin.password,
        }),
      report,
    });
  });

  test("Client UI link crawl", async ({ page }) => {
    await crawlApp({
      page,
      app: "client",
      baseUrl: CLIENT_BASE_URL,
      login: (loginPage) =>
        loginViaUi({
          page: loginPage,
          baseUrl: CLIENT_BASE_URL,
          emailValue: CREDENTIALS.client.email,
          passwordValue: CREDENTIALS.client.password,
        }),
      report,
    });
  });

  test("Partner UI link crawl", async ({ page }) => {
    await crawlApp({
      page,
      app: "partner",
      baseUrl: PARTNER_BASE_URL,
      login: (loginPage) =>
        loginViaUi({
          page: loginPage,
          baseUrl: PARTNER_BASE_URL,
          emailValue: CREDENTIALS.partner.email,
          passwordValue: CREDENTIALS.partner.password,
        }),
      report,
    });
  });
});

import path from "node:path";
import { expect, type Page } from "@playwright/test";

export const CLIENT_BASE_URL = process.env.CLIENT_PORTAL_URL ?? "http://localhost:4174";
export const PARTNER_BASE_URL = process.env.PARTNER_PORTAL_URL ?? "http://localhost:4175";
export const ADMIN_BASE_URL = process.env.ADMIN_PORTAL_URL ?? "http://localhost:4173";

const resolveEnv = (value: string | undefined, fallback: string) => (value && value.trim() !== "" ? value : fallback);
const requireEnv = (value: string | undefined, name: string) => {
  if (!value || value.trim() === "") {
    throw new Error(`Missing required env: ${name}`);
  }
  return value;
};

const loginWaitOptions = { timeout: 15_000 };

const emailSelector = [
  'input[type="email"]',
  'input[name="email"]',
  'input[autocomplete="email"]',
  'input[placeholder*="mail" i]',
  'input[placeholder*="email" i]',
  'input[id*="email" i]',
  'input[data-testid*="email" i]',
].join(", ");

const passwordSelector = [
  'input[type="password"]',
  'input[name="password"]',
  'input[autocomplete="current-password"]',
  'input[placeholder*="password" i]',
  'input[placeholder*="парол" i]',
  'input[id*="pass" i]',
  'input[data-testid*="pass" i]',
].join(", ");

async function resolvePasswordInput(page: Page) {
  const pass = page.locator(passwordSelector).first();
  if ((await pass.count()) > 0) {
    return pass;
  }
  const labelInput = page.getByLabel(/пароль/i).first();
  if ((await labelInput.count()) > 0) {
    return labelInput;
  }
  return page
    .locator("label:has-text('Пароль'), label:has-text('Password')")
    .first()
    .locator("input")
    .first();
}

async function buildLoginDiagnostics(page: Page, reason: string) {
  const url = page.url();
  const title = await page.title();
  const bodyText = await page.locator("body").innerText();
  const snippet = bodyText.replace(/\s+/g, " ").trim().slice(0, 200);
  return `${reason}. URL: ${url}. Title: ${title}. Body: ${snippet}`;
}

async function hasLoggedInShell(page: Page) {
  const sidebar = page.locator("nav, aside, [data-testid='app-shell'], [data-testid='sidebar']");
  const logoutButton = page.locator("button:has-text('Выйти'), button:has-text('Logout'), a:has-text('Выйти'), a:has-text('Logout')");
  if ((await sidebar.count()) > 0 && (await sidebar.first().isVisible().catch(() => false))) {
    return true;
  }
  if ((await logoutButton.count()) > 0 && (await logoutButton.first().isVisible().catch(() => false))) {
    return true;
  }
  return false;
}

export async function loginClient(page: Page) {
  await page.goto(`${CLIENT_BASE_URL}/login`, { waitUntil: "domcontentloaded", timeout: loginWaitOptions.timeout });
  await page.waitForLoadState("domcontentloaded");
  const email = page.locator(emailSelector).first();
  const pass = await resolvePasswordInput(page);
  await expect(email).toBeVisible(loginWaitOptions);
  await expect(pass).toBeVisible(loginWaitOptions);
  await email.fill(resolveEnv(process.env.NEFT_BOOTSTRAP_CLIENT_EMAIL, process.env.CLIENT_EMAIL ?? "client@neft.local"));
  await pass.fill(resolveEnv(process.env.NEFT_BOOTSTRAP_CLIENT_PASSWORD, process.env.CLIENT_PASSWORD ?? "client"));
  await page
    .locator('button[type="submit"], button:has-text("Войти"), button:has-text("Login"), button:has-text("Sign in")')
    .first()
    .click();
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), loginWaitOptions);
}

export async function loginPartner(page: Page) {
  await page.goto(`${PARTNER_BASE_URL}/login`, { waitUntil: "domcontentloaded", timeout: loginWaitOptions.timeout });
  await page.waitForLoadState("domcontentloaded");
  const email = page.locator(emailSelector).first();
  const pass = await resolvePasswordInput(page);
  await expect(email).toBeVisible(loginWaitOptions);
  await expect(pass).toBeVisible(loginWaitOptions);
  await email.fill(resolveEnv(process.env.NEFT_BOOTSTRAP_PARTNER_EMAIL, process.env.PARTNER_EMAIL ?? "partner@neft.local"));
  await pass.fill(resolveEnv(process.env.NEFT_BOOTSTRAP_PARTNER_PASSWORD, process.env.PARTNER_PASSWORD ?? "partner"));
  await page
    .locator('button[type="submit"], button:has-text("Войти"), button:has-text("Login"), button:has-text("Sign in")')
    .first()
    .click();
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), loginWaitOptions);
}

export async function loginAdmin(page: Page) {
  await page.goto(ADMIN_BASE_URL, { waitUntil: "domcontentloaded", timeout: loginWaitOptions.timeout });
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(500);
  console.log("LOGIN URL:", page.url());
  const screenshotPath = path.join(process.cwd(), "LOGIN_PAGE.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });
  const email = page.locator(emailSelector).first();
  const pass = await resolvePasswordInput(page);
  if ((await email.count()) === 0) {
    if (await hasLoggedInShell(page)) {
      return;
    }
    throw new Error(await buildLoginDiagnostics(page, "Login email input not found"));
  }
  if ((await pass.count()) === 0) {
    throw new Error(await buildLoginDiagnostics(page, "Login inputs not found"));
  }
  await expect(email).toBeVisible(loginWaitOptions);
  await expect(pass).toBeVisible(loginWaitOptions);
  await email.fill(resolveEnv(process.env.NEFT_BOOTSTRAP_ADMIN_EMAIL, process.env.ADMIN_EMAIL ?? "admin@example.com"));
  await pass.fill(requireEnv(process.env.NEFT_BOOTSTRAP_ADMIN_PASSWORD, "NEFT_BOOTSTRAP_ADMIN_PASSWORD"));
  await page
    .locator('button[type="submit"], button:has-text("Войти"), button:has-text("Login"), button:has-text("Sign in")')
    .first()
    .click();
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), loginWaitOptions);
}

export async function expectHeading(page: Page, pattern: RegExp) {
  await expect(page.getByRole("heading", { name: pattern })).toBeVisible();
}

export async function expectTableOrEmptyState(page: Page) {
  const table = page.locator("table");
  if ((await table.count()) > 0) {
    await expect(table.first()).toBeVisible();
  } else {
    await expect(page.locator(".empty-state").first()).toBeVisible();
  }
}

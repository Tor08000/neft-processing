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

export async function loginClient(page: Page) {
  await page.goto(`${CLIENT_BASE_URL}/login`, { waitUntil: "domcontentloaded", timeout: loginWaitOptions.timeout });
  await page.waitForLoadState("domcontentloaded");
  const email = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail" i]').first();
  const pass = page
    .locator('input[type="password"], input[name="password"], input[placeholder*="password" i], input[placeholder*="парол" i]')
    .first();
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
  const email = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail" i]').first();
  const pass = page
    .locator('input[type="password"], input[name="password"], input[placeholder*="password" i], input[placeholder*="парол" i]')
    .first();
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
  await page.goto(`${ADMIN_BASE_URL}/login`, { waitUntil: "domcontentloaded", timeout: loginWaitOptions.timeout });
  await page.waitForLoadState("domcontentloaded");
  const email = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail" i]').first();
  const pass = page
    .locator('input[type="password"], input[name="password"], input[placeholder*="password" i], input[placeholder*="парол" i]')
    .first();
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

import { expect, type Page } from "@playwright/test";

export const CLIENT_BASE_URL = process.env.CLIENT_PORTAL_URL ?? "http://localhost:4174";
export const PARTNER_BASE_URL = process.env.PARTNER_PORTAL_URL ?? "http://localhost:4175";
export const ADMIN_BASE_URL = process.env.ADMIN_PORTAL_URL ?? "http://localhost:4173";

const resolveEnv = (value: string | undefined, fallback: string) => (value && value.trim() !== "" ? value : fallback);

const defaultWaitOptions = { timeout: 20_000 };

export async function loginClient(page: Page) {
  await page.goto(`${CLIENT_BASE_URL}/login`);
  await page
    .getByLabel(/email/i)
    .fill(resolveEnv(process.env.NEFT_BOOTSTRAP_CLIENT_EMAIL, process.env.CLIENT_EMAIL ?? "client@neft.local"));
  await page
    .getByLabel(/пароль|password/i)
    .fill(resolveEnv(process.env.NEFT_BOOTSTRAP_CLIENT_PASSWORD, process.env.CLIENT_PASSWORD ?? "client"));
  await page.getByRole("button", { name: /войти|sign in|login/i }).click();
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), defaultWaitOptions);
}

export async function loginPartner(page: Page) {
  await page.goto(`${PARTNER_BASE_URL}/login`);
  await page
    .getByLabel(/email/i)
    .fill(resolveEnv(process.env.NEFT_BOOTSTRAP_PARTNER_EMAIL, process.env.PARTNER_EMAIL ?? "partner@neft.local"));
  await page
    .getByLabel(/пароль|password/i)
    .fill(resolveEnv(process.env.NEFT_BOOTSTRAP_PARTNER_PASSWORD, process.env.PARTNER_PASSWORD ?? "partner"));
  await page.getByRole("button", { name: /войти|sign in|login/i }).click();
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), defaultWaitOptions);
}

export async function loginAdmin(page: Page) {
  await page.goto(`${ADMIN_BASE_URL}/login`);
  await page
    .getByLabel(/email/i)
    .fill(resolveEnv(process.env.NEFT_BOOTSTRAP_ADMIN_EMAIL, process.env.ADMIN_EMAIL ?? "admin@example.com"));
  await page
    .getByLabel(/пароль|password/i)
    .fill(resolveEnv(process.env.NEFT_BOOTSTRAP_ADMIN_PASSWORD, process.env.ADMIN_PASSWORD ?? "admin123"));
  await page.getByRole("button", { name: /войти|sign in|login/i }).click();
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), defaultWaitOptions);
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

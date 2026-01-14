import path from "node:path";
import type { Page } from "playwright";

export const CLIENT_BASE_URL = process.env.CLIENT_PORTAL_URL ?? "http://localhost:4174";
export const PARTNER_BASE_URL = process.env.PARTNER_PORTAL_URL ?? "http://localhost:4175";
export const ADMIN_BASE_URL = process.env.ADMIN_PORTAL_URL ?? "http://localhost:4173";
export const ADMIN_AUTH_URL = process.env.ADMIN_AUTH_URL ?? "http://localhost/api/auth/v1/auth/login";

export type LoginState = "LOGIN_READY" | "LOGIN_SERVICE_DOWN" | "ALREADY_AUTHENTICATED" | "LOGIN_INPUTS_NOT_FOUND";

export type LoginSignals = {
  hasEmailInput: boolean;
  hasPasswordInput: boolean;
  hasSubmit: boolean;
  hasAuthenticatedShell: boolean;
  hasAuthCookie: boolean;
  hasAppShell: boolean;
};

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

const submitSelector = [
  'button[type="submit"]',
  'button:has-text("Войти")',
  'button:has-text("Login")',
  'button:has-text("Sign in")',
].join(", ");

async function hasAppShell(page: Page) {
  const shell = page.locator(
    "nav, aside, [data-testid='app-shell'], [data-testid='layout'], header, [data-testid='header'], [data-testid='topbar'], [role='navigation']",
  );
  const count = await shell.count();
  for (let index = 0; index < count; index += 1) {
    if (await shell.nth(index).isVisible().catch(() => false)) {
      return true;
    }
  }
  return false;
}

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

async function hasAuthCookie(page: Page) {
  const cookies = await page.context().cookies();
  return cookies.some((cookie) => /auth|token|session/i.test(cookie.name));
}

async function buildLoginDiagnostics(page: Page, reason: string) {
  const url = page.url();
  const title = await page.title();
  const bodyText = await page.locator("body").innerText();
  const snippet = bodyText.replace(/\s+/g, " ").trim().slice(0, 200);
  return `${reason}. URL: ${url}. Title: ${title}. Body: ${snippet}. Auth URL: ${ADMIN_AUTH_URL}.`;
}

async function hasLoggedInShell(page: Page) {
  const sidebar = page.locator("nav, aside, [data-testid='app-shell'], [data-testid='sidebar']");
  const logoutButton = page.locator(
    "button:has-text('Выйти'), button:has-text('Logout'), a:has-text('Выйти'), a:has-text('Logout')",
  );
  const currentUrl = page.url();
  const isDashboard = ["/dashboard", "/orders", "/home"].some((segment) => currentUrl.includes(segment));
  if (isDashboard) {
    return true;
  }
  if ((await sidebar.count()) > 0 && (await sidebar.first().isVisible().catch(() => false))) {
    return true;
  }
  if ((await logoutButton.count()) > 0 && (await logoutButton.first().isVisible().catch(() => false))) {
    return true;
  }
  return false;
}

async function checkAuthAvailability(page: Page) {
  try {
    const response = await page.request.fetch(ADMIN_AUTH_URL, { method: "GET", timeout: 5_000 });
    return response.status() < 500;
  } catch {
    return false;
  }
}

async function isAuthServiceDown(page: Page, authResult?: { type: "response"; status: number } | { type: "failed" } | null) {
  if (authResult?.type === "failed") {
    return true;
  }
  if (authResult?.type === "response") {
    return authResult.status >= 500;
  }
  return !(await checkAuthAvailability(page));
}

async function resolveLoginState(page: Page, signals: LoginSignals, authResult?: { type: "response"; status: number } | { type: "failed" } | null): Promise<LoginState> {
  if (signals.hasAuthenticatedShell) {
    return "ALREADY_AUTHENTICATED";
  }
  if (signals.hasEmailInput && signals.hasPasswordInput) {
    return "LOGIN_READY";
  }
  if (signals.hasAppShell) {
    return "LOGIN_INPUTS_NOT_FOUND";
  }
  const authDown = await isAuthServiceDown(page, authResult);
  return authDown ? "LOGIN_SERVICE_DOWN" : "LOGIN_INPUTS_NOT_FOUND";
}

async function hasVisibleLocator(locator: ReturnType<Page["locator"]>) {
  if ((await locator.count()) === 0) {
    return false;
  }
  return locator.first().isVisible().catch(() => false);
}

async function takeLoginScreenshot(page: Page, label: string) {
  const fileName = `login_${label}_${Date.now()}.png`;
  const filePath = path.join(process.cwd(), fileName);
  await page.screenshot({ path: filePath, fullPage: true });
  return filePath;
}

export async function getLoginSignals(page: Page): Promise<LoginSignals> {
  const email = page.locator(emailSelector);
  const pass = page.locator(passwordSelector);
  const submit = page.locator(submitSelector);
  const hasEmailInput = await hasVisibleLocator(email);
  const hasPasswordInput = await hasVisibleLocator(pass);
  const hasSubmit = await hasVisibleLocator(submit);
  const authCookiePresent = await hasAuthCookie(page);
  const hasAuthenticatedShell = (await hasLoggedInShell(page)) || authCookiePresent;
  const hasShell = await hasAppShell(page);
  return {
    hasEmailInput,
    hasPasswordInput,
    hasSubmit,
    hasAuthenticatedShell,
    hasAuthCookie: authCookiePresent,
    hasAppShell: hasShell,
  };
}

export async function detectLoginState(page: Page): Promise<LoginState> {
  const signals = await getLoginSignals(page);
  return resolveLoginState(page, signals);
}

async function waitForAuthResult(page: Page) {
  const authPattern = /\/api\/auth\/v1\/auth\/login/i;
  const authResponsePromise = page
    .waitForResponse((response) => authPattern.test(response.url()), { timeout: 5_000 })
    .then((response) => ({ type: "response" as const, status: response.status() }))
    .catch(() => null);
  const authFailurePromise = page
    .waitForEvent("requestfailed", { predicate: (request) => authPattern.test(request.url()), timeout: 5_000 })
    .then(() => ({ type: "failed" as const }))
    .catch(() => null);
  return Promise.race([authResponsePromise, authFailurePromise]);
}

export async function loginViaUi({
  page,
  baseUrl,
  emailValue,
  passwordValue,
}: {
  page: Page;
  baseUrl: string;
  emailValue: string;
  passwordValue: string;
}): Promise<LoginState> {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: loginWaitOptions.timeout });
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(800);
  const initialSignals = await getLoginSignals(page);
  if (initialSignals.hasAuthenticatedShell) {
    return "ALREADY_AUTHENTICATED";
  }
  if (!initialSignals.hasEmailInput || !initialSignals.hasPasswordInput) {
    return resolveLoginState(page, initialSignals);
  }
  if (!initialSignals.hasSubmit) {
    return "LOGIN_READY";
  }

  const email = page.locator(emailSelector).first();
  const pass = await resolvePasswordInput(page);
  const submit = page.locator(submitSelector).first();
  await email.waitFor({ state: "visible", timeout: loginWaitOptions.timeout });
  await pass.waitFor({ state: "visible", timeout: loginWaitOptions.timeout });
  await submit.waitFor({ state: "visible", timeout: loginWaitOptions.timeout });
  await email.fill(emailValue);
  await pass.fill(passwordValue);
  const authResultPromise = waitForAuthResult(page);
  await submit.click();
  const authResult = await authResultPromise;
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(800);
  const postSignals = await getLoginSignals(page);
  return resolveLoginState(page, postSignals, authResult ?? null);
}

async function performLogin({
  page,
  baseUrl,
  emailValue,
  passwordValue,
  appLabel,
}: {
  page: Page;
  baseUrl: string;
  emailValue: string;
  passwordValue: string;
  appLabel: string;
}) {
  const result = await loginViaUi({ page, baseUrl, emailValue, passwordValue });
  if (result === "ALREADY_AUTHENTICATED") {
    return;
  }
  if (result === "LOGIN_INPUTS_NOT_FOUND") {
    const screenshotPath = await takeLoginScreenshot(page, `${appLabel}_LOGIN_INPUTS_NOT_FOUND`);
    throw new Error(await buildLoginDiagnostics(page, `LOGIN_INPUTS_NOT_FOUND (screenshot: ${screenshotPath})`));
  }
  if (result === "LOGIN_SERVICE_DOWN") {
    const screenshotPath = await takeLoginScreenshot(page, `${appLabel}_LOGIN_SERVICE_DOWN`);
    throw new Error(await buildLoginDiagnostics(page, `LOGIN_SERVICE_DOWN (screenshot: ${screenshotPath})`));
  }
  const screenshotPath = await takeLoginScreenshot(page, `${appLabel}_FAIL_REDIRECT_LOGIN`);
  throw new Error(await buildLoginDiagnostics(page, `FAIL_REDIRECT_LOGIN (screenshot: ${screenshotPath})`));
}

export async function loginClient(page: Page) {
  await performLogin({
    page,
    baseUrl: CLIENT_BASE_URL,
    emailValue: resolveEnv(process.env.NEFT_BOOTSTRAP_CLIENT_EMAIL, process.env.CLIENT_EMAIL ?? "client@neft.local"),
    passwordValue: resolveEnv(process.env.NEFT_BOOTSTRAP_CLIENT_PASSWORD, process.env.CLIENT_PASSWORD ?? "client"),
    appLabel: "client",
  });
}

export async function loginPartner(page: Page) {
  await performLogin({
    page,
    baseUrl: PARTNER_BASE_URL,
    emailValue: resolveEnv(process.env.NEFT_BOOTSTRAP_PARTNER_EMAIL, process.env.PARTNER_EMAIL ?? "partner@neft.local"),
    passwordValue: resolveEnv(process.env.NEFT_BOOTSTRAP_PARTNER_PASSWORD, process.env.PARTNER_PASSWORD ?? "partner"),
    appLabel: "partner",
  });
}

export async function loginAdmin(page: Page) {
  await performLogin({
    page,
    baseUrl: ADMIN_BASE_URL,
    emailValue: resolveEnv(process.env.NEFT_BOOTSTRAP_ADMIN_EMAIL, process.env.ADMIN_EMAIL ?? "admin@example.com"),
    passwordValue: requireEnv(process.env.NEFT_BOOTSTRAP_ADMIN_PASSWORD, "NEFT_BOOTSTRAP_ADMIN_PASSWORD"),
    appLabel: "admin",
  });
}

export async function expectHeading(page: Page, pattern: RegExp) {
  await page.getByRole("heading", { name: pattern }).waitFor({ state: "visible" });
}

export async function expectTableOrEmptyState(page: Page) {
  const table = page.locator("table");
  if ((await table.count()) > 0) {
    await table.first().waitFor({ state: "visible" });
  } else {
    await page.locator(".empty-state").first().waitFor({ state: "visible" });
  }
}

import path from "node:path";
import type { Page, Request, Response } from "playwright";

export const CLIENT_BASE_URL = process.env.CLIENT_PORTAL_URL ?? "http://localhost/client/";
export const PARTNER_BASE_URL = process.env.PARTNER_PORTAL_URL ?? "http://localhost/partner/";
export const ADMIN_BASE_URL = process.env.ADMIN_PORTAL_URL ?? "http://localhost/admin/";
export const ADMIN_AUTH_URL = process.env.ADMIN_AUTH_URL ?? "http://localhost/api/auth/v1/auth/login";

export type LoginState =
  | "LOGIN_READY"
  | "LOGIN_SERVICE_DOWN"
  | "LOGIN_BAD_ROUTE"
  | "ALREADY_AUTHENTICATED"
  | "LOGIN_INPUTS_NOT_FOUND"
  | "LOGIN_OK"
  | "LOGIN_STUCK_ON_LOGIN"
  | "FAIL_AUTH_TOKEN_NOT_STORED"
  | "FAIL_LOGIN_NOT_COMPLETED"
  | "FAIL_AUTH_URL_DUPLICATED";

export type LoginSignals = {
  hasEmailInput: boolean;
  hasPasswordInput: boolean;
  hasSubmit: boolean;
  hasAuthenticatedShell: boolean;
  hasAuthCookie: boolean;
  hasAuthStorageToken: boolean;
  hasAppShell: boolean;
};

export type TokenFound = {
  kind: "localStorage" | "sessionStorage" | "cookie" | "none";
  key: string | null;
};

export type AuthProbeResult = {
  authRequestSent: boolean;
  authBaseEnv: string;
  authEffectiveUrl: string | null;
  authResponseStatus: number | null;
  authResponseContentType: string | null;
  authResponseBodySnippet: string | null;
  authRequestFailedError: string | null;
  storageKeys: string[];
  cookieNames: string[];
  tokenFound: TokenFound;
  afterClickScreenshot?: string;
};

type AuthProbeOptions = {
  onProbe?: (result: AuthProbeResult) => void | Promise<void>;
  afterClickScreenshot?: (page: Page) => Promise<string>;
};

const resolveEnv = (value: string | undefined, fallback: string) => (value && value.trim() !== "" ? value : fallback);
const requireEnv = (value: string | undefined, name: string) => {
  if (!value || value.trim() === "") {
    throw new Error(`Missing required env: ${name}`);
  }
  return value;
};

const loginWaitOptions = { timeout: 15_000 };
const authProbeTimeoutMs = 8_000;
const authEndpointPattern = /\/api(?:\/api)*\/auth\/v1\/auth\/login(?:\?|$)/;
const strictAuthEndpointPattern = /\/api\/auth\/v1\/auth\/login(?:\?|$)/;

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

async function hasAuthStorageToken(page: Page) {
  try {
    const probe = await probeStorage(page);
    return probe.tokenFound.kind !== "none";
  } catch {
    return false;
  }
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

async function waitForAppShell(page: Page, timeoutMs = 6_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if ((await hasLoggedInShell(page)) || (await hasAppShell(page))) {
      return true;
    }
    await page.waitForTimeout(300);
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

async function resolveLoginState(
  page: Page,
  signals: LoginSignals,
  authResult?: { type: "response"; status: number } | { type: "failed" } | null,
): Promise<LoginState> {
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
  const authStorageToken = await hasAuthStorageToken(page);
  const hasAuthenticatedShell = (await hasLoggedInShell(page)) || authCookiePresent || authStorageToken;
  const hasShell = await hasAppShell(page);
  return {
    hasEmailInput,
    hasPasswordInput,
    hasSubmit,
    hasAuthenticatedShell,
    hasAuthCookie: authCookiePresent,
    hasAuthStorageToken: authStorageToken,
    hasAppShell: hasShell,
  };
}

export async function detectLoginState(page: Page): Promise<LoginState> {
  const signals = await getLoginSignals(page);
  return resolveLoginState(page, signals);
}

function matchesAuthEndpoint(url: string) {
  return authEndpointPattern.test(url);
}

function matchesStrictAuthEndpoint(url: string) {
  return strictAuthEndpointPattern.test(url);
}

function isAuthRequest(request: Request) {
  return matchesAuthEndpoint(request.url()) && request.method() === "POST";
}

function isAuthResponse(response: Response) {
  return matchesAuthEndpoint(response.url()) && response.request().method() === "POST";
}

async function waitForAuthEvent(page: Page) {
  const authResponsePromise = page
    .waitForResponse((response) => isAuthResponse(response), { timeout: authProbeTimeoutMs })
    .then((response) => ({ type: "response" as const, response }))
    .catch(() => null);
  const authFailurePromise = page
    .waitForEvent("requestfailed", { predicate: (request) => isAuthRequest(request), timeout: authProbeTimeoutMs })
    .then((request) => ({ type: "failed" as const, request }))
    .catch(() => null);
  return Promise.race([authResponsePromise, authFailurePromise]);
}

async function waitForLoginOutcome(page: Page, initialUrl: string, timeoutMs = 7_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const signals = await getLoginSignals(page);
    const currentUrl = page.url();
    const urlChanged = currentUrl !== initialUrl && !currentUrl.includes("/login");
    const hasSession = signals.hasAuthCookie || signals.hasAuthStorageToken;
    const hasShell = signals.hasAuthenticatedShell || signals.hasAppShell;
    if (hasSession && (hasShell || urlChanged)) {
      return true;
    }
    await page.waitForTimeout(300);
  }
  return false;
}

type StorageProbe = {
  localKeys: string[];
  sessionKeys: string[];
  combinedKeys: string[];
  tokenFound: TokenFound;
  tokenFoundByShortlist: boolean;
};

async function probeStorage(page: Page): Promise<StorageProbe> {
  return page.evaluate(() => {
    const shortlist = ["access_token", "token", "neft_token", "auth_token"];
    const localKeys = Object.keys(localStorage);
    const sessionKeys = Object.keys(sessionStorage);
    const combinedKeys = [
      ...localKeys.map((key) => `localStorage:${key}`),
      ...sessionKeys.map((key) => `sessionStorage:${key}`),
    ];
    const jwtRegex = /[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/;
    const looksLikeJwt = (value: string | null) => {
      if (!value) {
        return false;
      }
      const match = value.match(jwtRegex);
      if (!match) {
        return false;
      }
      const candidate = match[0];
      const parts = candidate.split(".");
      return parts.length === 3 && parts.every((part) => /^[A-Za-z0-9_-]+$/.test(part));
    };
    const checkShortlist = (
      storage: Storage,
      keys: string[],
      kind: "localStorage" | "sessionStorage",
    ): TokenFound | null => {
      for (const key of keys) {
        if (!shortlist.includes(key)) {
          continue;
        }
        const value = storage.getItem(key);
        if (value && value.length > 10) {
          return { kind, key };
        }
      }
      return null;
    };
    let tokenFound =
      checkShortlist(localStorage, localKeys, "localStorage") ??
      checkShortlist(sessionStorage, sessionKeys, "sessionStorage");
    const tokenFoundByShortlist = Boolean(tokenFound);
    if (!tokenFound) {
      for (const key of localKeys) {
        if (looksLikeJwt(localStorage.getItem(key))) {
          tokenFound = { kind: "localStorage", key };
          break;
        }
      }
    }
    if (!tokenFound) {
      for (const key of sessionKeys) {
        if (looksLikeJwt(sessionStorage.getItem(key))) {
          tokenFound = { kind: "sessionStorage", key };
          break;
        }
      }
    }
    return {
      localKeys,
      sessionKeys,
      combinedKeys,
      tokenFound: tokenFound ?? { kind: "none", key: null },
      tokenFoundByShortlist,
    };
  });
}

function sliceKeysForReport(keys: string[], limit: number) {
  return keys.slice(0, limit);
}

function looksLikeJwt(value: string | null) {
  if (!value) {
    return false;
  }
  const match = value.match(/[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/);
  if (!match) {
    return false;
  }
  const parts = match[0].split(".");
  return parts.length === 3 && parts.every((part) => /^[A-Za-z0-9_-]+$/.test(part));
}

async function buildAuthProbe({
  page,
  authEvent,
  afterClickScreenshot,
}: {
  page: Page;
  authEvent: Awaited<ReturnType<typeof waitForAuthEvent>> | null;
  afterClickScreenshot?: string;
}) {
  let authRequestSent = false;
  let authEffectiveUrl: string | null = null;
  let authResponseStatus: number | null = null;
  let authResponseContentType: string | null = null;
  let authResponseBodySnippet: string | null = null;
  let authRequestFailedError: string | null = null;
  let authResult: { type: "response"; status: number } | { type: "failed" } | null = null;

  if (authEvent?.type === "response") {
    authRequestSent = true;
    authEffectiveUrl = authEvent.response.url();
    authResponseStatus = authEvent.response.status();
    authResponseContentType = authEvent.response.headers()["content-type"] ?? null;
    authResult = { type: "response", status: authResponseStatus };
    const bodyText = await authEvent.response.text().catch(() => "");
    if (bodyText) {
      authResponseBodySnippet = bodyText.slice(0, 400);
    }
  } else if (authEvent?.type === "failed") {
    authRequestSent = true;
    authEffectiveUrl = authEvent.request.url();
    authRequestFailedError = authEvent.request.failure()?.errorText ?? "request failed";
    authResult = { type: "failed" };
  }

  await page.waitForTimeout(250);
  const storageProbe = await probeStorage(page).catch(() => null);
  const cookieJar = await page.context().cookies().catch(() => []);
  const cookieNames = cookieJar.map((cookie) => cookie.name);
  let tokenFound: TokenFound = storageProbe?.tokenFound ?? { kind: "none", key: null };
  if (tokenFound.kind === "none") {
    const cookieWithJwt = cookieJar.find((cookie) => looksLikeJwt(cookie.value));
    if (cookieWithJwt) {
      tokenFound = { kind: "cookie", key: cookieWithJwt.name };
    }
  }
  const storageKeyLimit = storageProbe?.tokenFoundByShortlist ? 20 : 50;
  const storageKeys = storageProbe ? sliceKeysForReport(storageProbe.combinedKeys, storageKeyLimit) : [];
  const probeResult: AuthProbeResult = {
    authRequestSent,
    authBaseEnv: ADMIN_AUTH_URL,
    authEffectiveUrl,
    authResponseStatus,
    authResponseContentType,
    authResponseBodySnippet,
    authRequestFailedError,
    storageKeys,
    cookieNames: sliceKeysForReport(cookieNames, 20),
    tokenFound,
    afterClickScreenshot,
  };

  return {
    authResult,
    probeResult,
  };
}

export async function loginViaUi({
  page,
  baseUrl,
  emailValue,
  passwordValue,
  authProbe,
}: {
  page: Page;
  baseUrl: string;
  emailValue: string;
  passwordValue: string;
  authProbe?: AuthProbeOptions;
}): Promise<LoginState> {
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: loginWaitOptions.timeout });
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(500);
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
  const initialUrl = page.url();
  const authEventPromise = waitForAuthEvent(page);
  const authSuccessPromise = page
    .waitForResponse(
      (response) => matchesStrictAuthEndpoint(response.url()) && response.request().method() === "POST" && response.status() === 200,
      { timeout: authProbeTimeoutMs },
    )
    .catch(() => null);
  await Promise.all([authSuccessPromise, submit.click()]);
  const afterClickScreenshot = await authProbe?.afterClickScreenshot?.(page);
  const [authEvent, authSuccessResponse] = await Promise.all([authEventPromise, authSuccessPromise]);
  const { authResult, probeResult } = await buildAuthProbe({
    page,
    authEvent,
    afterClickScreenshot,
  });
  if (authProbe?.onProbe) {
    await authProbe.onProbe(probeResult);
  }
  const loginOutcome = await waitForLoginOutcome(page, initialUrl);
  const appShellVisible = await waitForAppShell(page);
  const postSignals = await getLoginSignals(page);
  const hasSession =
    postSignals.hasAuthCookie || postSignals.hasAuthStorageToken || probeResult.tokenFound.kind !== "none";
  const hasShell = postSignals.hasAuthenticatedShell || postSignals.hasAppShell || appShellVisible;
  const urlChanged = page.url() !== initialUrl && !page.url().includes("/login");
  const authResponseStatus = probeResult.authResponseStatus ?? authSuccessResponse?.status() ?? null;
  const authResponseContentType =
    probeResult.authResponseContentType ?? authSuccessResponse?.headers()["content-type"] ?? null;
  const authStatusOk = authResponseStatus === 200;
  const authContentTypeOk = authResponseContentType?.includes("application/json") ?? false;
  const loginConfirmed = authStatusOk && hasSession && (hasShell || urlChanged);
  if (probeResult.authEffectiveUrl?.includes("/api/api")) {
    return "FAIL_AUTH_URL_DUPLICATED";
  }
  if (probeResult.authEffectiveUrl?.includes("/auth/auth")) {
    return "FAIL_AUTH_URL_DUPLICATED";
  }
  if ((authResponseStatus === 200 && !authContentTypeOk) || authResponseStatus === 404) {
    return "LOGIN_BAD_ROUTE";
  }
  if (authResponseStatus !== null && authResponseStatus >= 500) {
    return "LOGIN_SERVICE_DOWN";
  }
  if (authEvent === null) {
    return "LOGIN_SERVICE_DOWN";
  }
  if (loginConfirmed) {
    return "LOGIN_OK";
  }
  if (authStatusOk && hasSession) {
    return "LOGIN_STUCK_ON_LOGIN";
  }
  if (authStatusOk) {
    return "FAIL_AUTH_TOKEN_NOT_STORED";
  }
  if (loginOutcome) {
    return "FAIL_LOGIN_NOT_COMPLETED";
  }
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(500);
  const finalSignals = await getLoginSignals(page);
  const resolved = await resolveLoginState(page, finalSignals, authResult ?? null);
  if (resolved === "ALREADY_AUTHENTICATED") {
    return "LOGIN_OK";
  }
  if (resolved === "LOGIN_READY") {
    if (authResponseStatus === 200 && probeResult.tokenFound.kind !== "none") {
      return "LOGIN_STUCK_ON_LOGIN";
    }
    return "LOGIN_READY";
  }
  return resolved;
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
  if (result === "ALREADY_AUTHENTICATED" || result === "LOGIN_OK") {
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
  if (result === "LOGIN_STUCK_ON_LOGIN") {
    const screenshotPath = await takeLoginScreenshot(page, `${appLabel}_LOGIN_STUCK_ON_LOGIN`);
    throw new Error(await buildLoginDiagnostics(page, `FAIL_LOGIN_STUCK_ON_LOGIN (screenshot: ${screenshotPath})`));
  }
  if (result === "LOGIN_BAD_ROUTE") {
    const screenshotPath = await takeLoginScreenshot(page, `${appLabel}_LOGIN_BAD_ROUTE`);
    throw new Error(await buildLoginDiagnostics(page, `LOGIN_BAD_ROUTE (screenshot: ${screenshotPath})`));
  }
  if (result === "FAIL_LOGIN_NOT_COMPLETED") {
    const screenshotPath = await takeLoginScreenshot(page, `${appLabel}_FAIL_LOGIN_NOT_COMPLETED`);
    throw new Error(await buildLoginDiagnostics(page, `FAIL_LOGIN_NOT_COMPLETED (screenshot: ${screenshotPath})`));
  }
  if (result === "FAIL_AUTH_URL_DUPLICATED") {
    const screenshotPath = await takeLoginScreenshot(page, `${appLabel}_FAIL_AUTH_URL_DUPLICATED`);
    throw new Error(await buildLoginDiagnostics(page, `FAIL_AUTH_URL_DUPLICATED (screenshot: ${screenshotPath})`));
  }
  if (result === "FAIL_AUTH_TOKEN_NOT_STORED") {
    const screenshotPath = await takeLoginScreenshot(page, `${appLabel}_FAIL_AUTH_TOKEN_NOT_STORED`);
    throw new Error(await buildLoginDiagnostics(page, `FAIL_AUTH_TOKEN_NOT_STORED (screenshot: ${screenshotPath})`));
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

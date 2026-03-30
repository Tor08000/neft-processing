const normalizeEmail = (email?: string | null) => (email ?? "").trim().toLowerCase();

export const DEMO_CLIENT_EMAILS = new Set(["client@neft.local"]);
export const DEMO_PARTNER_EMAILS = new Set(["partner@neft.local"]);

const isTruthyFlag = (value: string | undefined) => {
  if (!value) return false;
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
};

const isVitestRuntime = () => {
  const env = (import.meta as ImportMeta & { env?: Record<string, string | boolean | undefined> }).env;
  if (env?.MODE === "test") return true;
  if (env?.VITEST === true || env?.VITEST === "true") return true;
  if (typeof process !== "undefined" && process.env?.VITEST === "true") return true;
  return false;
};

export const isDemoModeEnabled = () => {
  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
  return isTruthyFlag(env?.VITE_DEMO_MODE) || isVitestRuntime();
};

const isDemoEmail = (email: string, allowed: Set<string>) => {
  if (!email) return false;
  if (allowed.has(email)) return true;
  return isDemoModeEnabled() && email.endsWith("@demo.test");
};

export const isDemoClient = (email?: string | null) => {
  const normalized = normalizeEmail(email);
  return isDemoEmail(normalized, DEMO_CLIENT_EMAILS);
};

export const isDemoPartner = (email?: string | null) => {
  const normalized = normalizeEmail(email);
  return isDemoEmail(normalized, DEMO_PARTNER_EMAILS);
};

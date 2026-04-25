const normalizeEmail = (email?: string | null) => (email ?? "").trim().toLowerCase();

export const DEMO_CLIENT_EMAILS = new Set(["client@neft.local"]);
export const DEMO_PARTNER_EMAILS = new Set(["partner@neft.local"]);
export const DEMO_ADMIN_EMAILS = new Set(["admin@neft.local"]);

const isTruthyFlag = (value: string | undefined) => {
  if (!value) return false;
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
};

const readDemoModeFlag = () => {
  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
  const processEnv =
    typeof process !== "undefined" && process.env
      ? (process.env.VITE_DEMO_MODE as string | undefined)
      : undefined;

  return env?.VITE_DEMO_MODE ?? processEnv;
};

export const isDemoModeEnabled = () => {
  return isTruthyFlag(readDemoModeFlag());
};

const isDemoEmail = (email: string, allowed: Set<string>) => {
  if (!email) return false;
  if (!isDemoModeEnabled()) return false;
  if (allowed.has(email)) return true;
  return email.endsWith("@demo.test");
};

export const isDemoClient = (email?: string | null) => {
  const normalized = normalizeEmail(email);
  return isDemoEmail(normalized, DEMO_CLIENT_EMAILS);
};

export const isDemoPartner = (email?: string | null) => {
  const normalized = normalizeEmail(email);
  return isDemoEmail(normalized, DEMO_PARTNER_EMAILS);
};

export const isDemoAdmin = (email?: string | null) => {
  const normalized = normalizeEmail(email);
  return isDemoEmail(normalized, DEMO_ADMIN_EMAILS);
};

const normalizeEmail = (email?: string | null) => (email ?? "").trim().toLowerCase();

export const DEMO_CLIENT_EMAILS = new Set(["client@neft.local"]);
export const DEMO_PARTNER_EMAILS = new Set(["partner@neft.local"]);

const isTruthyFlag = (value: string | undefined) => {
  if (!value) return false;
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
};

export const isDemoModeEnabled = () => {
  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
  return isTruthyFlag(env?.VITE_DEMO_MODE);
};

const isDemoEmail = (email: string, allowed: Set<string>) => {
  if (!isDemoModeEnabled()) return false;
  if (!email) return false;
  return allowed.has(email) || email.endsWith("@demo.test");
};

export const isDemoClient = (email?: string | null) => {
  const normalized = normalizeEmail(email);
  return isDemoEmail(normalized, DEMO_CLIENT_EMAILS);
};

export const isDemoPartner = (email?: string | null) => {
  const normalized = normalizeEmail(email);
  return isDemoEmail(normalized, DEMO_PARTNER_EMAILS);
};

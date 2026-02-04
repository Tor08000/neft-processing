const normalizeEmail = (email?: string | null) => (email ?? "").trim().toLowerCase();

export const DEMO_CLIENT_EMAILS = new Set(["client@neft.local"]);
export const DEMO_PARTNER_EMAILS = new Set(["partner@neft.local"]);

const isDemoEmail = (email: string, allowed: Set<string>) => {
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

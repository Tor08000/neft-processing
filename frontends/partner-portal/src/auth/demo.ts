const DEMO_PARTNER_EMAILS = new Set(["partner@neft.local"]);

export const isDemoPartnerEmail = (email?: string | null) => {
  if (!email) return false;
  const normalized = email.toLowerCase();
  return DEMO_PARTNER_EMAILS.has(normalized) || normalized.endsWith("@demo.test");
};

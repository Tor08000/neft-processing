const DEMO_CLIENT_EMAILS = new Set(["client@neft.local"]);

export const isDemoClientEmail = (email?: string | null) => {
  if (!email) return false;
  const normalized = email.toLowerCase();
  return DEMO_CLIENT_EMAILS.has(normalized) || normalized.endsWith("@demo.test");
};

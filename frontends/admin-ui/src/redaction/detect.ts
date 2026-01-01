export const EMAIL_REGEX = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i;
export const PHONE_REGEX = /\+?\d[\d\s().-]{7,}\d/;
export const BEARER_REGEX = /bearer\s+[A-Z0-9._-]+/i;
export const JWT_REGEX = /[A-Z0-9_-]+\.[A-Z0-9_-]+\.[A-Z0-9_-]+/i;
export const PAN_REGEX = /(?:\d[ -]?){13,19}/;
export const IBAN_REGEX = /[A-Z]{2}\d{2}[A-Z0-9]{10,30}/i;

export const normalizeDigits = (value: string) => value.replace(/\D/g, "");

export const findEmail = (value: string) => value.match(EMAIL_REGEX)?.[0] ?? null;

export const findPhone = (value: string) => value.match(PHONE_REGEX)?.[0] ?? null;

export const findPan = (value: string) => {
  const match = value.match(PAN_REGEX)?.[0];
  if (!match) return null;
  const digits = normalizeDigits(match);
  if (digits.length < 13 || digits.length > 19) return null;
  return { raw: match, digits };
};

export const findIban = (value: string) => value.match(IBAN_REGEX)?.[0] ?? null;

export const hasBearerToken = (value: string) => BEARER_REGEX.test(value);

export const hasJwt = (value: string) => JWT_REGEX.test(value);

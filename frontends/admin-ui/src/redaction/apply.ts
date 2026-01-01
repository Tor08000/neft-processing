import type { RedactedValue, RedactionKind, RedactionReason } from "./types";
import { matchFieldRule } from "./policy";
import {
  findEmail,
  findIban,
  findPan,
  findPhone,
  hasBearerToken,
  hasJwt,
  normalizeDigits,
} from "./detect";

type RedactionMode = "audit" | "viewer" | "export";

type RedactionResult = unknown | RedactedValue;

const REDACTION_DISPLAY = "REDACTED";
const HASH_LENGTH = 10;

const hashCache = new Map<string, string>();

const isRedactionEnabled = () => {
  if (typeof import.meta !== "undefined" && import.meta.env?.VITE_ADMIN_REDACTION) {
    return import.meta.env.VITE_ADMIN_REDACTION !== "off";
  }
  return true;
};

const simpleHash = (value: string) => {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  const hex = Math.abs(hash).toString(16);
  return hex.padStart(8, "0").slice(0, HASH_LENGTH);
};

const computeWebCryptoHash = async (value: string) => {
  if (typeof crypto === "undefined" || !crypto.subtle || typeof TextEncoder === "undefined") return null;
  try {
    const data = new TextEncoder().encode(value);
    const digest = await crypto.subtle.digest("SHA-256", data);
    const bytes = Array.from(new Uint8Array(digest));
    return bytes.map((byte) => byte.toString(16).padStart(2, "0")).join("").slice(0, HASH_LENGTH);
  } catch {
    return null;
  }
};

const getHash = (value: string) => {
  const cached = hashCache.get(value);
  if (cached) return cached;
  const fallback = simpleHash(value);
  hashCache.set(value, fallback);
  void computeWebCryptoHash(value).then((result) => {
    if (result) {
      hashCache.set(value, result);
    }
  });
  return fallback;
};

const buildReason = (kind: RedactionKind, rule: string, message: string): RedactionReason => ({
  kind,
  rule,
  message,
});

export const isRedactedValue = (value: unknown): value is RedactedValue =>
  Boolean(value && typeof value === "object" && (value as RedactedValue).redacted);

const maskEmail = (value: string) => {
  const match = findEmail(value);
  if (!match) return REDACTION_DISPLAY;
  const [local, domain] = match.split("@");
  if (!domain) return REDACTION_DISPLAY;
  const prefix = local.slice(0, Math.min(2, local.length));
  return `${prefix}***@${domain}`;
};

const maskPhone = (value: string) => {
  const digits = normalizeDigits(value);
  if (digits.length < 7) return REDACTION_DISPLAY;
  const last2 = digits.slice(-2);
  return `***-**-${last2}`;
};

const maskPan = (digits: string) => {
  const prefix = digits.slice(0, 6);
  const suffix = digits.slice(-4);
  const masked = "*".repeat(Math.max(0, digits.length - 10));
  return `${prefix}${masked}${suffix}`;
};

const maskBank = (value: string) => {
  const trimmed = value.replace(/\s/g, "");
  if (trimmed.length <= 8) return REDACTION_DISPLAY;
  const prefix = trimmed.slice(0, 4);
  const suffix = trimmed.slice(-4);
  return `${prefix}****${suffix}`;
};

const redactValue = (
  fieldPath: string,
  value: unknown,
  _mode: RedactionMode,
  includeHash: boolean,
): RedactionResult => {
  if (!isRedactionEnabled()) return value;
  const fieldRule = matchFieldRule(fieldPath);
  if (fieldRule) {
    const display =
      fieldRule.mask === "email" && typeof value === "string"
        ? maskEmail(value)
        : fieldRule.mask === "phone" && typeof value === "string"
          ? maskPhone(value)
          : fieldRule.mask === "card" && typeof value === "string"
            ? maskPan(normalizeDigits(value))
            : fieldRule.mask === "bank" && typeof value === "string"
              ? maskBank(value)
              : REDACTION_DISPLAY;
    return {
      redacted: true,
      display,
      hash: includeHash && value !== null && value !== undefined ? getHash(String(value)) : undefined,
      reason: buildReason(fieldRule.kind, fieldRule.id, fieldRule.message),
    };
  }

  if (typeof value !== "string") return value;

  if (hasBearerToken(value) || hasJwt(value)) {
    return {
      redacted: true,
      display: REDACTION_DISPLAY,
      hash: includeHash ? getHash(value) : undefined,
      reason: buildReason("secret", "value_contains_token", "Value looks like a secret token"),
    };
  }

  const email = findEmail(value);
  if (email) {
    if (email === value) {
      return {
        redacted: true,
        display: maskEmail(value),
        hash: includeHash ? getHash(value) : undefined,
        reason: buildReason("email", "value_is_email", "Value is an email"),
      };
    }
    return {
      redacted: true,
      display: value.replace(email, maskEmail(email)),
      hash: includeHash ? getHash(value) : undefined,
      reason: buildReason("free_text", "value_contains_email", "Free text contains an email"),
    };
  }

  const phone = findPhone(value);
  if (phone) {
    if (phone === value) {
      return {
        redacted: true,
        display: maskPhone(value),
        hash: includeHash ? getHash(value) : undefined,
        reason: buildReason("phone", "value_is_phone", "Value is a phone number"),
      };
    }
    return {
      redacted: true,
      display: value.replace(phone, maskPhone(phone)),
      hash: includeHash ? getHash(value) : undefined,
      reason: buildReason("free_text", "value_contains_phone", "Free text contains a phone number"),
    };
  }

  const panMatch = findPan(value);
  if (panMatch) {
    const { digits, raw } = panMatch;
    if (normalizeDigits(value) === digits) {
      return {
        redacted: true,
        display: maskPan(digits),
        hash: includeHash ? getHash(value) : undefined,
        reason: buildReason("card", "value_is_card", "Value looks like card PAN"),
      };
    }
    return {
      redacted: true,
      display: value.replace(raw, maskPan(digits)),
      hash: includeHash ? getHash(value) : undefined,
      reason: buildReason("free_text", "value_contains_card", "Free text contains card PAN"),
    };
  }

  const iban = findIban(value);
  if (iban) {
    if (iban === value) {
      return {
        redacted: true,
        display: maskBank(value),
        hash: includeHash ? getHash(value) : undefined,
        reason: buildReason("bank", "value_is_iban", "Value looks like IBAN or bank account"),
      };
    }
    return {
      redacted: true,
      display: value.replace(iban, maskBank(iban)),
      hash: includeHash ? getHash(value) : undefined,
      reason: buildReason("free_text", "value_contains_iban", "Free text contains bank account"),
    };
  }

  return value;
};

export const redactForAudit = (fieldPath: string, value: unknown): RedactionResult =>
  redactValue(fieldPath, value, "audit", true);

const redactDeep = (input: unknown, fieldPath: string, mode: RedactionMode): unknown => {
  const maybeRedacted = redactValue(fieldPath, input, mode, mode === "audit");
  if (isRedactedValue(maybeRedacted) || maybeRedacted === null || typeof maybeRedacted !== "object") {
    return maybeRedacted;
  }
  if (Array.isArray(maybeRedacted)) {
    return maybeRedacted.map((item, index) => redactDeep(item, `${fieldPath}[${index}]`, mode));
  }
  return Object.fromEntries(
    Object.entries(maybeRedacted as Record<string, unknown>).map(([key, value]) => [
      key,
      redactDeep(value, fieldPath ? `${fieldPath}.${key}` : key, mode),
    ]),
  );
};

export const redactObjectDeep = (
  input: unknown,
  opts?: { mode: RedactionMode | "off" },
): unknown => {
  const mode = opts?.mode ?? "viewer";
  if (mode === "off" || !isRedactionEnabled()) return input;
  return redactDeep(input, "", mode);
};

export const redactForExport = (input: unknown): unknown => redactObjectDeep(input, { mode: "export" });

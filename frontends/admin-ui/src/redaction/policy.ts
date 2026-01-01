import type { RedactionKind } from "./types";

type MaskStrategy = "full" | "email" | "phone" | "card" | "bank";

export type FieldRule = {
  id: string;
  kind: RedactionKind;
  message: string;
  mask: MaskStrategy;
  pattern: RegExp;
};

const buildFieldRegex = (terms: string[]) =>
  new RegExp(`(^|[._\\-\\s])(${terms.join("|")})($|[._\\-\\s])`, "i");

export const FIELD_RULES: FieldRule[] = [
  {
    id: "field_contains_secret",
    kind: "secret",
    message: "Field contains a secret token/password",
    mask: "full",
    pattern: buildFieldRegex([
      "password",
      "pass",
      "secret",
      "token",
      "api_key",
      "apikey",
      "authorization",
      "cookie",
      "session",
      "private_key",
    ]),
  },
  {
    id: "field_contains_email",
    kind: "email",
    message: "Field contains email",
    mask: "email",
    pattern: buildFieldRegex(["email"]),
  },
  {
    id: "field_contains_phone",
    kind: "phone",
    message: "Field contains phone number",
    mask: "phone",
    pattern: buildFieldRegex(["phone", "tel"]),
  },
  {
    id: "field_contains_card",
    kind: "card",
    message: "Field contains card PAN",
    mask: "card",
    pattern: buildFieldRegex(["card", "pan"]),
  },
  {
    id: "field_contains_bank",
    kind: "bank",
    message: "Field contains bank account",
    mask: "bank",
    pattern: buildFieldRegex(["iban", "account", "bank"]),
  },
  {
    id: "field_contains_address",
    kind: "pii",
    message: "Field contains address",
    mask: "full",
    pattern: buildFieldRegex(["address"]),
  },
  {
    id: "field_contains_identity",
    kind: "identifier",
    message: "Field contains document identifier",
    mask: "full",
    pattern: buildFieldRegex(["passport", "inn", "snils", "driver" ]),
  },
  {
    id: "field_contains_name",
    kind: "pii",
    message: "Field contains full name",
    mask: "full",
    pattern: new RegExp("(^|[._\\-\\s])(full_name|name)($|[._\\-\\s])", "i"),
  },
];

export const matchFieldRule = (fieldPath: string): FieldRule | null => {
  if (!fieldPath) return null;
  return FIELD_RULES.find((rule) => rule.pattern.test(fieldPath)) ?? null;
};

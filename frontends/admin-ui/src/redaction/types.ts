export type RedactionKind =
  | "secret"
  | "email"
  | "phone"
  | "card"
  | "bank"
  | "pii"
  | "identifier"
  | "free_text";

export type RedactionReason = {
  kind: RedactionKind;
  rule: string;
  message: string;
};

export type RedactedValue = {
  redacted: true;
  display: string;
  hash?: string;
  reason: RedactionReason;
};

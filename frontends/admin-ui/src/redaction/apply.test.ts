import { describe, expect, it } from "vitest";
import { isRedactedValue, redactForAudit } from "./apply";

const expectRedacted = (value: unknown) => {
  expect(isRedactedValue(value)).toBe(true);
  return value;
};

describe("redaction", () => {
  it("redacts password fields", () => {
    const result = redactForAudit("user.password", "super-secret");
    expectRedacted(result);
    if (isRedactedValue(result)) {
      expect(result.display).toBe("REDACTED");
      expect(result.reason.kind).toBe("secret");
    }
  });

  it("masks email values", () => {
    const result = redactForAudit("user.email", "user@example.com");
    expectRedacted(result);
    if (isRedactedValue(result)) {
      expect(result.display).toBe("us***@example.com");
      expect(result.reason.kind).toBe("email");
    }
  });

  it("masks phone values", () => {
    const result = redactForAudit("contact.phone", "+7 999 123 45 12");
    expectRedacted(result);
    if (isRedactedValue(result)) {
      expect(result.display).toBe("***-**-12");
      expect(result.reason.kind).toBe("phone");
    }
  });

  it("redacts bearer tokens", () => {
    const result = redactForAudit("headers.Authorization", "Bearer abc.def.ghi");
    expectRedacted(result);
    if (isRedactedValue(result)) {
      expect(result.display).toBe("REDACTED");
      expect(result.reason.kind).toBe("secret");
    }
  });

  it("masks PAN values", () => {
    const result = redactForAudit("payment.card", "4111111111111111");
    expectRedacted(result);
    if (isRedactedValue(result)) {
      expect(result.display).toBe("411111******1111");
      expect(result.reason.kind).toBe("card");
    }
  });

  it("masks phone inside free text", () => {
    const result = redactForAudit("note", "call me +7 999 123 45 12");
    expectRedacted(result);
    if (isRedactedValue(result)) {
      expect(result.display).toContain("***-**-12");
      expect(result.reason.kind).toBe("free_text");
    }
  });

  it("produces stable hashes", () => {
    const first = redactForAudit("token", "secret-1");
    const second = redactForAudit("token", "secret-1");
    expectRedacted(first);
    expectRedacted(second);
    if (isRedactedValue(first) && isRedactedValue(second)) {
      expect(first.hash).toBeTruthy();
      expect(first.hash).toBe(second.hash);
    }
  });
});

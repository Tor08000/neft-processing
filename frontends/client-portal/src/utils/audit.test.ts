import { describe, expect, it } from "vitest";
import { getActorLabel, getAuditEventLabel } from "./audit";

describe("audit event mapping", () => {
  it("maps event types to labels", () => {
    expect(getAuditEventLabel("INVOICE_CREATED")).toBe("Счет создан");
  });

  it("maps actor types to labels", () => {
    expect(getActorLabel("USER")).toBe("Вы");
    expect(getActorLabel("SERVICE")).toBe("Сервис");
    expect(getActorLabel("SYSTEM")).toBe("Система");
  });
});

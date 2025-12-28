import { describe, expect, it } from "vitest";
import { buildAuditSearchQuery, buildInvoiceAuditQuery } from "./audit";

describe("audit query builder", () => {
  it("builds invoice audit query with filters", () => {
    const query = buildInvoiceAuditQuery({
      dateFrom: "2024-01-01",
      dateTo: "2024-01-31",
      eventType: ["INVOICE_CREATED", "PAYMENT_POSTED"],
      limit: 25,
      offset: 10,
    });
    const params = new URLSearchParams(query);
    expect(params.get("date_from")).toBe("2024-01-01");
    expect(params.get("date_to")).toBe("2024-01-31");
    expect(params.getAll("event_type")).toEqual(["INVOICE_CREATED", "PAYMENT_POSTED"]);
    expect(params.get("limit")).toBe("25");
    expect(params.get("offset")).toBe("10");
  });

  it("builds external ref search query", () => {
    const query = buildAuditSearchQuery({
      externalRef: "BANK-123",
      provider: "bank",
      dateFrom: "2024-01-01",
    });
    const params = new URLSearchParams(query);
    expect(params.get("external_ref")).toBe("BANK-123");
    expect(params.get("provider")).toBe("bank");
    expect(params.get("date_from")).toBe("2024-01-01");
  });
});

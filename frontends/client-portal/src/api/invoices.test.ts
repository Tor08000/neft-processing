import { describe, expect, it } from "vitest";
import { buildInvoiceQuery } from "./invoices";

describe("invoice query builder", () => {
  it("builds query with date range and status filters", () => {
    const query = buildInvoiceQuery({
      dateFrom: "2024-01-01",
      dateTo: "2024-01-31",
      status: ["SENT", "PAID"],
      limit: 25,
      offset: 50,
    });
    const params = new URLSearchParams(query);
    expect(params.get("date_from")).toBe("2024-01-01");
    expect(params.get("date_to")).toBe("2024-01-31");
    expect(params.getAll("status")).toEqual(["SENT", "PAID"]);
    expect(params.get("limit")).toBe("25");
    expect(params.get("offset")).toBe("50");
  });
});

import { describe, expect, it } from "vitest";
import { getInvoiceStatusLabel, getInvoiceStatusTone } from "./invoices";

describe("invoice status mapping", () => {
  it("maps status to label and badge tone", () => {
    expect(getInvoiceStatusLabel("SENT")).toBe("Выставлен");
    expect(getInvoiceStatusTone("SENT")).toBe("warn");
  });
});

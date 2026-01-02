import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import BillingInvoiceDetailsPage from "./BillingInvoiceDetailsPage";
import * as billingApi from "../../api/billing";

vi.mock("../../api/billing", () => ({
  getInvoice: vi.fn(),
  listInvoicePayments: vi.fn(),
  listReconciliationLinks: vi.fn(),
  refundPayment: vi.fn(),
}));

describe("BillingInvoiceDetailsPage", () => {
  it("renders payments tab", async () => {
    (billingApi.getInvoice as ReturnType<typeof vi.fn>).mockResolvedValue({
      invoice: {
        id: "inv_1",
        invoice_number: "INV-001",
        client_id: "client_1",
        case_id: null,
        currency: "RUB",
        amount_total: 1000,
        amount_paid: 200,
        status: "ISSUED",
        issued_at: "2024-01-01T00:00:00Z",
        due_at: null,
        ledger_tx_id: "tx_1",
        audit_event_id: "audit_1",
        created_at: "2024-01-01T00:00:00Z",
      },
    });
    (billingApi.listInvoicePayments as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          id: "pay_1",
          invoice_id: "inv_1",
          provider: "bank_stub",
          provider_payment_id: "prov_1",
          currency: "RUB",
          amount: 200,
          captured_at: "2024-01-02T00:00:00Z",
          status: "CAPTURED",
          ledger_tx_id: "tx_2",
          audit_event_id: "audit_2",
          created_at: "2024-01-02T00:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    (billingApi.listReconciliationLinks as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });

    render(
      <MemoryRouter initialEntries={["/billing/invoices/inv_1"]}>
        <Routes>
          <Route path="/billing/invoices/:id" element={<BillingInvoiceDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("pay_1")).toBeInTheDocument());
    expect(screen.getByText("Payments")).toBeInTheDocument();
  });
});

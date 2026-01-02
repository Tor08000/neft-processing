import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import BillingInvoicesPage from "./BillingInvoicesPage";
import * as billingApi from "../../api/billing";

vi.mock("../../api/billing", () => ({
  listInvoices: vi.fn(),
  createInvoice: vi.fn(),
  captureInvoicePayment: vi.fn(),
}));

describe("BillingInvoicesPage", () => {
  beforeEach(() => {
    (billingApi.listInvoices as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
  });

  it("renders invoices list", async () => {
    (billingApi.listInvoices as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
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
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });

    render(
      <MemoryRouter>
        <BillingInvoicesPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("INV-001")).toBeInTheDocument());
    expect(screen.getByText("client_1")).toBeInTheDocument();
  });

  it("validates issue invoice modal", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <BillingInvoicesPage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Issue invoice" }));
    const buttons = screen.getAllByRole("button", { name: "Issue invoice" });
    await user.click(buttons[buttons.length - 1]);

    expect(await screen.findByText("Client ID is required")).toBeInTheDocument();
  });
});

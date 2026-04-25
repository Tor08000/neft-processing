import React from "react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import BillingPaymentDetailsPage from "./BillingPaymentDetailsPage";
import * as billingApi from "../../api/billing";

vi.mock("../../api/billing", () => ({
  getPayment: vi.fn(),
  listRefunds: vi.fn(),
  refundPayment: vi.fn(),
}));

vi.mock("../../components/common/Toast", () => ({
  Toast: () => null,
}));

vi.mock("../../components/common/JsonViewer", () => ({
  JsonViewer: () => <div>json-viewer</div>,
}));

vi.mock("../../components/Toast/useToast", () => ({
  useToast: () => ({
    toast: null,
    showToast: vi.fn(),
  }),
}));

function renderPage(path = "/billing/payments/pay-1") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/billing/payments/:id" element={<BillingPaymentDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("BillingPaymentDetailsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders an honest unavailable state when the payment owner route is not mounted", async () => {
    (billingApi.getPayment as ReturnType<typeof vi.fn>).mockResolvedValue({ payment: null, unavailable: true });
    (billingApi.listRefunds as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
      limit: 0,
      offset: 0,
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "Контур платежей недоступен" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "К списку платежей" })).toBeInTheDocument();
  });

  it("distinguishes refunds unavailable from a genuine empty refunds history", async () => {
    (billingApi.getPayment as ReturnType<typeof vi.fn>).mockResolvedValue({
      payment: {
        id: "pay-1",
        invoice_id: "inv-1",
        provider: "test",
        provider_payment_id: "provider-pay-1",
        currency: "RUB",
        amount: 1200,
        captured_at: "2026-04-15T10:00:00Z",
        status: "CAPTURED",
        ledger_tx_id: "ledger-1",
        audit_event_id: "audit-1",
        created_at: "2026-04-15T10:00:00Z",
      },
    });
    (billingApi.listRefunds as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
      limit: 0,
      offset: 0,
      unavailable: true,
    });

    renderPage();

    expect(await screen.findByText("Payment pay-1")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Возвраты временно недоступны" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("heading", { name: "No refunds" })).not.toBeInTheDocument());
  });
});

import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import InvoiceDetailsPage from "./InvoiceDetailsPage";
import FinanceOverviewPage from "./FinanceOverviewPage";
import PaymentIntakesPage from "./PaymentIntakesPage";
import PayoutDetailsPage from "./PayoutDetailsPage";
import PayoutQueuePage from "./PayoutQueuePage";
import * as financeApi from "../../api/finance";
import * as auditApi from "../../api/audit";
import { buildAdminPermissions } from "../../admin/access";

vi.mock("../../api/finance", () => ({
  fetchFinanceOverview: vi.fn(),
  fetchFinanceInvoice: vi.fn(),
  markInvoicePaid: vi.fn(),
  voidInvoice: vi.fn(),
  markInvoiceOverdue: vi.fn(),
  fetchPaymentIntakes: vi.fn(),
  fetchPaymentIntake: vi.fn(),
  approvePaymentIntake: vi.fn(),
  rejectPaymentIntake: vi.fn(),
  fetchPayoutDetail: vi.fn(),
  fetchPartnerLedger: vi.fn(),
  fetchPartnerSettlement: vi.fn(),
  approvePayout: vi.fn(),
  rejectPayout: vi.fn(),
  markPayoutPaid: vi.fn(),
  fetchPayoutQueue: vi.fn(),
}));

vi.mock("../../api/audit", () => ({
  fetchAuditCorrelation: vi.fn(),
}));

vi.mock("../../admin/AdminContext", () => ({
  useAdmin: () => ({
    profile: {
      permissions: buildAdminPermissions(["NEFT_FINANCE"]),
      read_only: false,
    },
  }),
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    accessToken: "token-1",
  }),
}));

function renderWithProviders(element: React.ReactElement, initialEntries = ["/"]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={initialEntries}>{element}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Finance detail pages", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    (auditApi.fetchAuditCorrelation as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [] });
    (financeApi.fetchPartnerLedger as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [] });
    (financeApi.fetchPartnerSettlement as ReturnType<typeof vi.fn>).mockResolvedValue({});
  });

  it("renders invoice state explain and owner timeline", async () => {
    (financeApi.fetchFinanceInvoice as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "inv-1",
      org_id: "org-1",
      subscription_id: "sub-1",
      status: "OVERDUE",
      period_start: "2026-03-01",
      period_end: "2026-03-31",
      due_at: "2026-04-01T00:00:00Z",
      paid_at: null,
      total: "12500.00",
      currency: "RUB",
      pdf_url: "https://example.test/invoice.pdf",
      state_explain: {
        current_status: "OVERDUE",
        pdf_status: "READY",
        has_pdf: true,
        is_overdue: true,
        payment_intakes_total: 2,
        payment_intakes_pending: 1,
        latest_payment_intake_status: "APPROVED",
        reconciliation_request_id: "recon-1",
      },
      timeline: [
        {
          ts: "2026-04-02T10:00:00Z",
          event_type: "SUBSCRIPTION_INVOICE_OVERDUE",
          entity_type: "billing_invoice",
          entity_id: "inv-1",
          action: "OVERDUE",
          reason: "due_date_elapsed",
        },
      ],
    });

    renderWithProviders(
      <Routes>
        <Route path="/finance/invoices/:invoiceId" element={<InvoiceDetailsPage />} />
      </Routes>,
      ["/finance/invoices/inv-1"],
    );

    await waitFor(() => expect(screen.getByText("State explain")).toBeInTheDocument());
    expect(screen.getByText("Payment intakes: 2")).toBeInTheDocument();
    expect(screen.getByText(/SUBSCRIPTION_INVOICE_OVERDUE/)).toBeInTheDocument();
  });

  it("renders finance overview cards and switches window", async () => {
    (financeApi.fetchFinanceOverview as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        overdue_orgs: 4,
        overdue_amount: "120000.00",
        invoices_issued_24h: 12,
        invoices_paid_24h: 8,
        payment_intakes_pending: 3,
        reconciliation_unmatched_24h: 2,
        payout_queue_pending: 5,
        mor_immutable_violations_24h: 1,
        clawback_required_24h: 0,
        payout_blocked_top_reasons: [{ reason: "MISSING_SETTLEMENT", count: 2 }],
      })
      .mockResolvedValueOnce({
        overdue_orgs: 6,
        overdue_amount: "160000.00",
        invoices_issued_24h: 18,
        invoices_paid_24h: 10,
        payment_intakes_pending: 4,
        reconciliation_unmatched_24h: 3,
        payout_queue_pending: 7,
        mor_immutable_violations_24h: 1,
        clawback_required_24h: 1,
        payout_blocked_top_reasons: [{ reason: "LEGAL_HOLD", count: 3 }],
      });

    renderWithProviders(<FinanceOverviewPage />, ["/finance"]);

    await waitFor(() => expect(screen.getByText("Overdue orgs")).toBeInTheDocument());
    expect(financeApi.fetchFinanceOverview).toHaveBeenCalledWith("24h");
    expect(screen.getByText("MISSING_SETTLEMENT: 2")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "7d" }));

    await waitFor(() => expect(financeApi.fetchFinanceOverview).toHaveBeenLastCalledWith("7d"));
    expect(screen.getByText("LEGAL_HOLD: 3")).toBeInTheDocument();
  });

  it("shows selected payment intake timeline from canonical detail route", async () => {
    (financeApi.fetchPaymentIntakes as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          id: 101,
          org_id: 100,
          invoice_id: "inv-101",
          status: "UNDER_REVIEW",
          amount: "12500.00",
          currency: "RUB",
          created_by_user_id: "client-user-1",
          invoice_link: "/finance/invoices/inv-101",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    (financeApi.fetchPaymentIntake as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 101,
      org_id: 100,
      invoice_id: "inv-101",
      status: "APPROVED",
      amount: "12500.00",
      currency: "RUB",
      created_by_user_id: "client-user-1",
      invoice_status: "PAID",
      invoice_link: "/finance/invoices/inv-101",
      timeline: [
        {
          ts: "2026-04-02T11:00:00Z",
          event_type: "PAYMENT_INTAKE_APPROVED",
          entity_type: "billing_payment_intake",
          entity_id: "101",
          action: "APPROVE",
          reason: "bank statement matched",
        },
      ],
    });

    renderWithProviders(<PaymentIntakesPage />, ["/finance/payment-intakes"]);

    await waitFor(() => expect(screen.getByText("101")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Details" }));

    await waitFor(() => expect(screen.getByText("Selected intake")).toBeInTheDocument());
    expect(screen.getByText("Invoice status: PAID")).toBeInTheDocument();
    expect(screen.getByText(/PAYMENT_INTAKE_APPROVED/)).toBeInTheDocument();
    expect(screen.getByText("Visible intakes: 1 / 1")).toBeInTheDocument();
  });

  it("renders payout queue filters and correlation actions inside the shared table shell", async () => {
    (financeApi.fetchPayoutQueue as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          payout_id: "payout-queue-1",
          partner_org: "partner-77",
          amount: "1500.00",
          net_amount: "1450.00",
          currency: "RUB",
          status: "BLOCKED",
          block_reason: "LEGAL_HOLD",
          blockers: ["LEGAL_HOLD"],
          correlation_id: "corr-queue-1",
          created_at: "2026-04-03T11:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });

    renderWithProviders(<PayoutQueuePage />, ["/finance/payouts"]);

    await waitFor(() => expect(screen.getByText("payout-queue-1")).toBeInTheDocument());
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", "/audit?correlation_id=corr-queue-1");
    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
    expect(screen.getByText("Visible payouts: 1 / 1")).toBeInTheDocument();
  });

  it("renders payout explain from owner payload without stale field fallbacks", async () => {
    (financeApi.fetchPayoutDetail as ReturnType<typeof vi.fn>).mockResolvedValue({
      payout_id: "payout-1",
      partner_org: "partner-1",
      amount: "1500.00",
      currency: "RUB",
      status: "REQUESTED",
      blockers: ["MIN_THRESHOLD"],
      block_reason: "MIN_THRESHOLD",
      legal_status: "VERIFIED",
      settlement_state: "APPROVED",
      correlation_id: "corr-1",
      correlation_chain: ["corr-1"],
      policy: {
        min_payout_amount: "2000.00",
        payout_hold_days: 0,
        payout_schedule: "WEEKLY",
      },
      settlement_snapshot: {
        settlement_id: "set-1",
        breakdown: { gross: "5000.0000", net: "4750.0000" },
      },
      block_reason_tree: {
        blockers: ["MIN_THRESHOLD"],
        policy: { min_payout_amount: "2000.00" },
      },
      audit_events: [
        {
          ts: "2026-04-02T12:00:00Z",
          event_type: "partner_payout_requested",
          entity_type: "partner_payout_request",
          entity_id: "payout-1",
          action: "partner_payout_requested",
        },
      ],
      trace: [
        {
          entity_type: "partner_ledger_entry:PAYOUT_REQUESTED",
          entity_id: "entry-1",
          amount: "1500.00",
          currency: "RUB",
        },
      ],
      totals: { gross: "1500.00", fee: "0", penalties: "0", net: "1500.00" },
    });

    renderWithProviders(
      <Routes>
        <Route path="/finance/payouts/:payoutId" element={<PayoutDetailsPage />} />
      </Routes>,
      ["/finance/payouts/payout-1"],
    );

    await waitFor(() => expect(screen.getByText("Payout payout-1")).toBeInTheDocument());
    expect(screen.getByText("Settlement status")).toBeInTheDocument();
    expect(screen.getByText("APPROVED")).toBeInTheDocument();
    expect(screen.getByText("Primary blocker: MIN_THRESHOLD")).toBeInTheDocument();
    expect(screen.getByText(/partner_payout_requested/)).toBeInTheDocument();
  });
});

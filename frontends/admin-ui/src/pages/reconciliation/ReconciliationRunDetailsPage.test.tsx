import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ReconciliationRunDetailsPage from "./ReconciliationRunDetailsPage";
import * as reconciliationApi from "../../api/reconciliation";

vi.mock("../../api/reconciliation", () => ({
  downloadRunExport: vi.fn(),
  getDiscrepancy: vi.fn(),
  getRun: vi.fn(),
  listDiscrepancies: vi.fn(),
  listRunLinks: vi.fn(),
  resolveDiscrepancy: vi.fn(),
  ignoreDiscrepancy: vi.fn(),
}));

describe("ReconciliationRunDetailsPage", () => {
  beforeEach(() => {
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:mock"),
      revokeObjectURL: vi.fn(),
    });
    HTMLAnchorElement.prototype.click = vi.fn();
    (reconciliationApi.getRun as unknown as Mock).mockResolvedValue({
      run: {
        id: "run_1",
        scope: "internal",
        provider: null,
        period_start: "2024-01-01T00:00:00Z",
        period_end: "2024-01-31T00:00:00Z",
        status: "completed",
        created_at: "2024-02-01T00:00:00Z",
        summary: { mismatches_found: 1, total_delta_abs: 50 },
        statement: {
          id: "stmt_1",
          provider: "bank_stub",
          period_start: "2024-01-01T00:00:00Z",
          period_end: "2024-01-31T00:00:00Z",
          currency: "USD",
          total_in: 100,
          total_out: 50,
          closing_balance: 50,
          created_at: "2024-02-01T00:00:00Z",
          source_hash: "hash-1",
        },
        link_counts: { matched: 1, mismatched: 1, pending: 0 },
        timeline: [
          {
            ts: "2024-02-01T00:00:00Z",
            event_type: "RECONCILIATION_RUN_COMPLETED",
            entity_type: "reconciliation_run",
            entity_id: "run_1",
            action: "completed",
          },
        ],
      },
    });
    (reconciliationApi.listDiscrepancies as unknown as Mock).mockResolvedValue({
      discrepancies: [
        {
          id: "disc_1",
          run_id: "run_1",
          ledger_account_id: "acc_1",
          currency: "USD",
          discrepancy_type: "balance_mismatch",
          internal_amount: 100,
          external_amount: 110,
          delta: 10,
          details: { reason: "test" },
          status: "resolved",
          resolution: { adjustment_tx_id: "tx_1" },
          created_at: "2024-02-01T00:00:00Z",
        },
      ],
    });
    (reconciliationApi.getDiscrepancy as unknown as Mock).mockResolvedValue({
      discrepancy: {
        id: "disc_1",
        run_id: "run_1",
        ledger_account_id: "acc_1",
        currency: "USD",
        discrepancy_type: "balance_mismatch",
        internal_amount: 100,
        external_amount: 110,
        delta: 10,
        details: { reason: "test" },
        status: "resolved",
        resolution: { adjustment_tx_id: "tx_1" },
        created_at: "2024-02-01T00:00:00Z",
        timeline: [
          {
            ts: "2024-02-01T01:00:00Z",
            event_type: "DISCREPANCY_RESOLVED",
            entity_type: "reconciliation_discrepancy",
            entity_id: "disc_1",
            action: "resolved",
          },
          {
            ts: "2024-02-01T00:00:00Z",
            event_type: "DISCREPANCY_DETECTED",
            entity_type: "reconciliation_discrepancy",
            entity_id: "disc_1",
            action: "created",
          },
        ],
        adjustment_explain: {
          adjustment_tx_id: "tx_1",
          transaction_type: "ADJUSTMENT",
          external_ref_type: "RECONCILIATION_DISCREPANCY",
          external_ref_id: "disc_1",
          tenant_id: 1,
          currency: "USD",
          total_amount: 10,
          meta: { discrepancy_id: "disc_1" },
          audit_events: [
            {
              ts: "2024-02-01T01:00:00Z",
              event_type: "ledger_transaction",
              entity_type: "internal_ledger_transaction",
              entity_id: "tx_1",
              action: "ADJUSTMENT",
            },
          ],
          entries: [
            {
              account_id: "acc_1",
              account_type: "CLIENT_AR",
              direction: "DEBIT",
              amount: 10,
              currency: "USD",
              entry_hash: "hash-1",
            },
            {
              account_id: "acc_2",
              account_type: "SUSPENSE",
              direction: "CREDIT",
              amount: 10,
              currency: "USD",
              entry_hash: "hash-2",
            },
          ],
        },
      },
    });
    (reconciliationApi.listRunLinks as unknown as Mock).mockResolvedValue({
      links: [
        {
          id: "link_1",
          entity_type: "invoice",
          entity_id: "inv_1",
          provider: "bank_stub",
          currency: "USD",
          expected_amount: 110,
          direction: "IN",
          status: "mismatched",
          expected_at: "2024-02-01T00:00:00Z",
          created_at: "2024-02-01T00:00:00Z",
          discrepancy_ids: ["disc_1"],
          review_status: "open",
        },
      ],
    });
    (reconciliationApi.resolveDiscrepancy as unknown as Mock).mockResolvedValue({ adjustment_tx_id: "tx_1" });
    (reconciliationApi.downloadRunExport as unknown as Mock).mockResolvedValue({
      blob: new Blob(["{}"], { type: "application/json" }),
      fileName: "reconciliation_run_run_1.json",
      contentType: "application/json",
    });
  });

  it("loads discrepancy detail from canonical owner and downloads backend-owned exports", async () => {
    render(
      <MemoryRouter initialEntries={["/reconciliation/runs/run_1"]}>
        <Routes>
          <Route path="/reconciliation/runs/:id" element={<ReconciliationRunDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("disc_1")).toBeInTheDocument());
    expect(screen.getAllByText("balance_mismatch").length).toBeGreaterThan(0);
    expect(screen.getByText("stmt_1")).toBeInTheDocument();
    expect(screen.getByText("RECONCILIATION_RUN_COMPLETED")).toBeInTheDocument();
    fireEvent.click(screen.getByText("View"));
    await waitFor(() => expect(reconciliationApi.getDiscrepancy).toHaveBeenCalledWith("disc_1"));
    await waitFor(() => expect(screen.getByText("Adjustment explain")).toBeInTheDocument());
    expect(screen.getByText("DISCREPANCY_RESOLVED")).toBeInTheDocument();
    expect(screen.getByText(/RECONCILIATION_DISCREPANCY/)).toBeInTheDocument();
    const [scopeSelect, statusSelect, typeSelect] = screen.getAllByRole("combobox");
    fireEvent.change(scopeSelect, { target: { value: "discrepancies" } });
    fireEvent.change(statusSelect, { target: { value: "resolved" } });
    fireEvent.change(typeSelect, { target: { value: "balance_mismatch" } });
    fireEvent.click(screen.getByText("Export JSON"));
    await waitFor(() =>
      expect(reconciliationApi.downloadRunExport).toHaveBeenCalledWith("run_1", "json", {
        export_scope: "discrepancies",
        discrepancy_status: "resolved",
        discrepancy_type: "balance_mismatch",
      }),
    );
    fireEvent.click(screen.getByText("Export CSV"));
    await waitFor(() =>
      expect(reconciliationApi.downloadRunExport).toHaveBeenCalledWith("run_1", "csv", {
        export_scope: "discrepancies",
        discrepancy_status: "resolved",
        discrepancy_type: "balance_mismatch",
      }),
    );
  });

  it("resolves discrepancy", async () => {
    (reconciliationApi.listDiscrepancies as unknown as Mock).mockResolvedValueOnce({
      discrepancies: [
        {
          id: "disc_1",
          run_id: "run_1",
          ledger_account_id: "acc_1",
          currency: "USD",
          discrepancy_type: "balance_mismatch",
          internal_amount: 100,
          external_amount: 110,
          delta: 10,
          details: { reason: "test" },
          status: "open",
          created_at: "2024-02-01T00:00:00Z",
        },
      ],
    });
    render(
      <MemoryRouter initialEntries={["/reconciliation/runs/run_1"]}>
        <Routes>
          <Route path="/reconciliation/runs/:id" element={<ReconciliationRunDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("disc_1")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Resolve"));
    fireEvent.change(screen.getByPlaceholderText(/Provide a detailed note/i), {
      target: { value: "Resolved discrepancy note" },
    });
    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => expect(screen.getByText("resolved")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Links"));
    await waitFor(() => expect(screen.getByText("link_1")).toBeInTheDocument());
    expect(screen.getByText("invoice")).toBeInTheDocument();
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import ReconciliationStatementsPage from "./ReconciliationStatementsPage";
import * as reconciliationApi from "../../api/reconciliation";

vi.mock("../../api/reconciliation", () => ({
  listStatements: vi.fn(),
  getStatement: vi.fn(),
  listStatementDiscrepancies: vi.fn(),
  getDiscrepancy: vi.fn(),
  uploadStatement: vi.fn(),
  createExternalRun: vi.fn(),
}));

describe("ReconciliationStatementsPage", () => {
  beforeEach(() => {
    (reconciliationApi.listStatements as unknown as Mock).mockResolvedValue({
      statements: [
        {
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
      ],
    });
    (reconciliationApi.getStatement as unknown as Mock).mockResolvedValue({
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
        explain: {
          related_run_id: "run_1",
          related_run_status: "completed",
          relation_source: "summary",
          line_count: 2,
          matched_links: 1,
          mismatched_links: 1,
          pending_links: 0,
          unmatched_external: 1,
          unmatched_internal: 0,
          mismatched_amount: 1,
          open_discrepancies: 1,
          resolved_discrepancies: 1,
          ignored_discrepancies: 0,
          adjusted_discrepancies: 1,
          total_checks: [
            {
              kind: "closing_balance",
              status: "mismatch",
              external_amount: 50,
              internal_amount: 40,
              delta: 10,
              discrepancy_id: "disc_2",
            },
          ],
        },
        timeline: [
          {
            ts: "2024-02-01T00:00:00Z",
            event_type: "EXTERNAL_STATEMENT_UPLOADED",
            entity_type: "external_statement",
            entity_id: "stmt_1",
            action: "created",
          },
        ],
      },
    });
    (reconciliationApi.listStatementDiscrepancies as unknown as Mock).mockResolvedValue({
      discrepancies: [
        {
          id: "disc_1",
          run_id: "run_1",
          currency: "USD",
          discrepancy_type: "mismatched_amount",
          internal_amount: 40,
          external_amount: 50,
          delta: 10,
          status: "resolved",
          created_at: "2024-02-01T00:30:00Z",
          adjustment_explain: {
            adjustment_tx_id: "tx_1",
            transaction_type: "ADJUSTMENT",
            total_amount: 10,
            currency: "USD",
            entries: [],
            audit_events: [],
          },
        },
      ],
    });
    (reconciliationApi.getDiscrepancy as unknown as Mock).mockResolvedValue({
      discrepancy: {
        id: "disc_2",
        run_id: "run_1",
        currency: "USD",
        discrepancy_type: "balance_mismatch",
        internal_amount: 40,
        external_amount: 50,
        delta: 10,
        status: "resolved",
        created_at: "2024-02-01T00:30:00Z",
        details: { statement_id: "stmt_1" },
        resolution: { adjustment_tx_id: "tx_1" },
        adjustment_explain: {
          adjustment_tx_id: "tx_1",
          transaction_type: "ADJUSTMENT",
          external_ref_type: "RECONCILIATION_DISCREPANCY",
          external_ref_id: "disc_2",
          total_amount: 10,
          currency: "USD",
          entries: [],
          audit_events: [],
        },
        timeline: [
          {
            ts: "2024-02-01T00:30:00Z",
            event_type: "DISCREPANCY_RESOLVED",
            entity_type: "reconciliation_discrepancy",
            entity_id: "disc_2",
            action: "resolved",
          },
        ],
      },
    });
    (reconciliationApi.uploadStatement as unknown as Mock).mockResolvedValue({ statement: null });
  });

  it("validates upload modal", async () => {
    render(
      <MemoryRouter>
        <ReconciliationStatementsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Upload statement")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Upload statement"));

    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "Bank" } });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "USD" } });
    fireEvent.change(screen.getByLabelText("Period start"), { target: { value: "2024-01-01T00:00" } });
    fireEvent.change(screen.getByLabelText("Period end"), { target: { value: "2024-01-02T00:00" } });
    fireEvent.change(screen.getByLabelText("Lines JSON"), { target: { value: "{invalid" } });

    fireEvent.click(screen.getByText("Upload"));

    await waitFor(() => expect(screen.getByText("Lines must be valid JSON")).toBeInTheDocument());
  });

  it("renders statement explain, statement discrepancies and dedicated discrepancy drilldown", async () => {
    render(
      <MemoryRouter>
        <ReconciliationStatementsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("stmt_1")).toBeInTheDocument());
    fireEvent.click(screen.getByText("View"));

    await waitFor(() => expect(screen.getByText("Statement explain")).toBeInTheDocument());
    expect(screen.getByText("run_1")).toBeInTheDocument();
    expect(screen.getByText("closing_balance")).toBeInTheDocument();
    expect(screen.getByText("EXTERNAL_STATEMENT_UPLOADED")).toBeInTheDocument();
    expect(screen.getByText("Statement discrepancies")).toBeInTheDocument();
    expect(screen.getByText("mismatched_amount")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Open discrepancy disc_2"));
    await waitFor(() => expect(reconciliationApi.getDiscrepancy).toHaveBeenCalledWith("disc_2"));
    await waitFor(() => expect(screen.getByText("Discrepancy disc_2")).toBeInTheDocument());
    expect(screen.getByText("DISCREPANCY_RESOLVED")).toBeInTheDocument();
  });
});

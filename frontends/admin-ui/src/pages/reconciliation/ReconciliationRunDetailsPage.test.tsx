import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ReconciliationRunDetailsPage from "./ReconciliationRunDetailsPage";
import * as reconciliationApi from "../../api/reconciliation";

vi.mock("../../api/reconciliation", () => ({
  getRun: vi.fn(),
  listDiscrepancies: vi.fn(),
  resolveDiscrepancy: vi.fn(),
  ignoreDiscrepancy: vi.fn(),
}));

describe("ReconciliationRunDetailsPage", () => {
  beforeEach(() => {
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
          status: "open",
          created_at: "2024-02-01T00:00:00Z",
        },
      ],
    });
    (reconciliationApi.resolveDiscrepancy as unknown as Mock).mockResolvedValue({ adjustment_tx_id: "tx_1" });
  });

  it("renders discrepancies", async () => {
    render(
      <MemoryRouter initialEntries={["/reconciliation/runs/run_1"]}>
        <Routes>
          <Route path="/reconciliation/runs/:id" element={<ReconciliationRunDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("disc_1")).toBeInTheDocument());
    expect(screen.getByText("balance_mismatch")).toBeInTheDocument();
  });

  it("resolves discrepancy", async () => {
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
  });
});

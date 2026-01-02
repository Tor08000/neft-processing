import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import ReconciliationRunsPage from "./ReconciliationRunsPage";
import * as reconciliationApi from "../../api/reconciliation";

vi.mock("../../api/reconciliation", () => ({
  listRuns: vi.fn(),
  listStatements: vi.fn(),
  createInternalRun: vi.fn(),
  createExternalRun: vi.fn(),
}));

describe("ReconciliationRunsPage", () => {
  beforeEach(() => {
    (reconciliationApi.listRuns as unknown as Mock).mockResolvedValue({ runs: [] });
  });

  it("renders empty state", async () => {
    render(
      <MemoryRouter>
        <ReconciliationRunsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("No runs yet")).toBeInTheDocument());
    expect(screen.getByText("Reconciliation")).toBeInTheDocument();
  });

  it("renders runs table rows", async () => {
    (reconciliationApi.listRuns as unknown as Mock).mockResolvedValue({
      runs: [
        {
          id: "run_1",
          scope: "internal",
          provider: null,
          period_start: "2024-01-01T00:00:00Z",
          period_end: "2024-01-31T00:00:00Z",
          status: "completed",
          created_at: "2024-02-01T00:00:00Z",
          summary: { mismatches_found: 2, total_delta_abs: 1200 },
        },
      ],
    });

    render(
      <MemoryRouter>
        <ReconciliationRunsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("run_1")).toBeInTheDocument());
    expect(screen.getAllByText("completed").length).toBeGreaterThan(0);
  });
});

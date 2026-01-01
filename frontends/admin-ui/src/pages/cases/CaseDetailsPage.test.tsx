import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CaseDetailsPage from "./CaseDetailsPage";
import * as adminCasesApi from "../../api/adminCases";
import * as masteryEvents from "../../mastery/events";

vi.mock("../../api/adminCases", () => ({
  fetchAdminCaseDetails: vi.fn(),
  fetchAdminCaseEvents: vi.fn(),
  closeAdminCase: vi.fn(),
  updateAdminCaseStatus: vi.fn(),
  isNotAvailableError: vi.fn(() => false),
}));

vi.mock("../../mastery/events", () => ({
  recordCaseClosed: vi.fn(),
  recordActionApplied: vi.fn(),
}));

const baseCase = {
  id: "case-1",
  status: "OPEN",
  priority: "HIGH",
  title: "Suspicious order",
  note: "Investigate unusual pattern",
  created_at: "2024-01-01T10:00:00Z",
  created_by: "risk@neft.io",
  updated_at: "2024-01-01T11:00:00Z",
  closed_at: null,
  closed_by: null,
  kind: "order",
};

const explainSnapshot = {
  id: "snap-1",
  created_at: "2024-01-01T10:01:00Z",
  explain_snapshot: {
    kind: "operation",
    id: "op-1",
    decision: "REVIEW",
    score: 0.42,
    score_band: "review",
    generated_at: "2024-01-01T10:01:00Z",
    evidence: [],
    documents: [],
    recommended_actions: [],
  },
  diff_snapshot: { meta: { kind: "operation", left: { snapshot_id: "a", label: "a" }, right: { snapshot_id: "b", label: "b" } }, score_diff: {}, decision_diff: {}, reasons_diff: [], evidence_diff: [] },
  selected_actions: [{ code: "ACTION_BLOCK" }],
};

describe("CaseDetailsPage", () => {
  beforeEach(() => {
    (adminCasesApi.fetchAdminCaseDetails as unknown as Mock).mockResolvedValue({
      case: baseCase,
      latest_snapshot: explainSnapshot,
      snapshots: [explainSnapshot],
    });
    (adminCasesApi.fetchAdminCaseEvents as unknown as Mock).mockResolvedValue({ items: [] });
    (adminCasesApi.closeAdminCase as unknown as Mock).mockResolvedValue({
      ...baseCase,
      status: "CLOSED",
      closed_at: "2024-01-02T10:00:00Z",
    });
  });

  it("renders tabs", async () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1"]}>
        <Routes>
          <Route path="/cases/:id" element={<CaseDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByRole("button", { name: "Explain JSON" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Diff JSON" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Selected actions" })).toBeInTheDocument();
  });

  it("closes case and records mastery event", async () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1"]}>
        <Routes>
          <Route path="/cases/:id" element={<CaseDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Suspicious order")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Close Case" }));

    const submitButton = await screen.findByRole("button", { name: "Close case" });
    expect(submitButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText("Summary of how the case was resolved"), {
      target: { value: "Resolved after review and mitigation applied." },
    });
    expect(submitButton).not.toBeDisabled();

    fireEvent.click(screen.getByLabelText("Actions were applied (1)"));
    fireEvent.click(submitButton);

    await waitFor(() => expect(screen.getByText("CLOSED")).toBeInTheDocument());
    expect(masteryEvents.recordCaseClosed).toHaveBeenCalled();
    expect(masteryEvents.recordActionApplied).toHaveBeenCalled();
  });
});

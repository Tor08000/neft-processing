import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CaseDetailsPage from "./CaseDetailsPage";
import * as adminCasesApi from "../../api/adminCases";
import * as masteryEvents from "../../mastery/events";

vi.mock("../../api/adminCases", () => ({
  fetchAdminCaseDetails: vi.fn(),
  listCaseEvents: vi.fn(),
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
    localStorage.clear();
    (adminCasesApi.fetchAdminCaseDetails as unknown as Mock).mockResolvedValue({
      case: baseCase,
      latest_snapshot: explainSnapshot,
      snapshots: [explainSnapshot],
    });
    (adminCasesApi.listCaseEvents as unknown as Mock).mockResolvedValue({ items: [] });
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

  it("renders timeline with real events", async () => {
    (adminCasesApi.listCaseEvents as unknown as Mock).mockResolvedValue({
      items: [
        {
          id: "evt-1",
          at: "2024-01-02T10:00:00Z",
          type: "STATUS_CHANGED",
          actor: { email: "ops@neft.io", name: "Ops" },
          request_id: "req-1",
          trace_id: "trace-1",
          meta: {
            changes: [{ field: "status", from: "OPEN", to: "IN_PROGRESS" }],
            export_ref: { kind: "explain_export", id: "exp-1", url: "/api/admin/exports/exp-1" },
          },
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/cases/case-1"]}>
        <Routes>
          <Route path="/cases/:id" element={<CaseDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Audit timeline")).toBeInTheDocument());
    const timeline = screen.getByTestId("audit-timeline");
    expect(within(timeline).getByText("Status changed")).toBeInTheDocument();
    expect(within(timeline).getByText("status")).toBeInTheDocument();
    expect(within(timeline).getByText("IN_PROGRESS")).toBeInTheDocument();
    expect(within(timeline).getByText("Request ID")).toBeInTheDocument();
    expect(within(timeline).getByText("Trace ID")).toBeInTheDocument();
    const exportLink = within(timeline).getByRole("link", { name: "Open export" });
    expect(exportLink).toHaveAttribute("href", "/api/admin/exports/exp-1");
  });

  it("falls back to synthetic events when unavailable", async () => {
    (adminCasesApi.listCaseEvents as unknown as Mock).mockResolvedValue({ items: [], unavailable: true });

    render(
      <MemoryRouter initialEntries={["/cases/case-1"]}>
        <Routes>
          <Route path="/cases/:id" element={<CaseDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Audit timeline")).toBeInTheDocument());
    const timeline = screen.getByTestId("audit-timeline");
    expect(within(timeline).getByText("Case created")).toBeInTheDocument();
  });
});

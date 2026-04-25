import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CaseDetailsPage from "./CaseDetailsPage";
import * as casesApi from "../../api/cases";
import * as adminCasesApi from "../../api/adminCases";
import * as adminExportsApi from "../../api/adminExports";
import * as decisionMemoryApi from "../../api/decisionMemory";
import * as masteryEvents from "../../mastery/events";
import { buildAdminPermissions } from "../../admin/access";

const useAdminMock = vi.fn();

vi.mock("../../api/cases", () => ({
  fetchCaseDetails: vi.fn(),
}));

vi.mock("../../api/adminCases", () => ({
  listCaseEvents: vi.fn(),
  closeAdminCase: vi.fn(),
  updateAdminCaseStatus: vi.fn(),
  isNotAvailableError: vi.fn(() => false),
}));

vi.mock("../../api/adminExports", () => ({
  listCaseExports: vi.fn(),
  downloadCaseExport: vi.fn(),
  verifyCaseExport: vi.fn(),
}));

vi.mock("../../api/decisionMemory", () => ({
  listDecisionMemory: vi.fn(),
}));

vi.mock("../../mastery/events", () => ({
  recordCaseClosed: vi.fn(),
  recordActionApplied: vi.fn(),
}));

vi.mock("../../admin/AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

const baseCase = {
  id: "case-1",
  tenant_id: 1,
  kind: "order",
  entity_type: "ORDER",
  entity_id: "order-1",
  title: "Suspicious order",
  description: "Customer reported order issue",
  status: "TRIAGE",
  queue: "SUPPORT",
  priority: "HIGH",
  escalation_level: 0,
  first_response_due_at: null,
  resolve_due_at: null,
  sla_state: "ON_TRACK",
  client_id: "client-1",
  partner_id: "partner-1",
  created_by: "risk@neft.io",
  assigned_to: null,
  case_source_ref_type: "MARKETPLACE_ORDER",
  case_source_ref_id: "order-1",
  created_at: "2024-01-01T10:00:00Z",
  updated_at: "2024-01-01T11:00:00Z",
  last_activity_at: "2024-01-01T11:00:00Z",
} as const;

const inProgressCase = {
  ...baseCase,
  status: "IN_PROGRESS",
  updated_at: "2024-01-01T12:00:00Z",
  last_activity_at: "2024-01-01T12:00:00Z",
} as const;

const closedCase = {
  ...baseCase,
  status: "CLOSED",
  updated_at: "2024-01-01T13:00:00Z",
  last_activity_at: "2024-01-01T13:00:00Z",
} as const;

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
  diff_snapshot: {
    meta: { kind: "operation", left: { snapshot_id: "a", label: "a" }, right: { snapshot_id: "b", label: "b" } },
    score_diff: {},
    decision_diff: {},
    reasons_diff: [],
    evidence_diff: [],
  },
  selected_actions: [{ code: "ACTION_BLOCK" }],
  note: "Investigate unusual pattern",
};

const buildDetailsResponse = (caseItem = baseCase) => ({
  case: caseItem,
  latest_snapshot: explainSnapshot,
  snapshots: [explainSnapshot],
  comments: [],
  timeline: [{ status: caseItem.status, occurred_at: caseItem.created_at }],
});

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/cases/case-1"]}>
      <Routes>
        <Route path="/cases/:id" element={<CaseDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("CaseDetailsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["NEFT_SUPPORT"]),
        read_only: false,
      },
    });
    (casesApi.fetchCaseDetails as unknown as Mock).mockResolvedValue(buildDetailsResponse());
    (adminCasesApi.listCaseEvents as unknown as Mock).mockResolvedValue({ items: [] });
    (adminCasesApi.updateAdminCaseStatus as unknown as Mock).mockResolvedValue(undefined);
    (adminExportsApi.listCaseExports as unknown as Mock).mockResolvedValue({ items: [] });
    (decisionMemoryApi.listDecisionMemory as unknown as Mock).mockResolvedValue({ items: [] });
    (adminCasesApi.closeAdminCase as unknown as Mock).mockResolvedValue(undefined);
  });

  it("renders tabs", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Explain JSON" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Diff JSON" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Selected actions" })).toBeInTheDocument();
    expect(screen.getByText("Customer reported order issue")).toBeInTheDocument();
    expect(screen.getByText("MARKETPLACE_ORDER · order-1")).toBeInTheDocument();
  });

  it("marks case in progress via backend and refreshes details", async () => {
    (casesApi.fetchCaseDetails as unknown as Mock)
      .mockResolvedValueOnce(buildDetailsResponse())
      .mockResolvedValueOnce(buildDetailsResponse(inProgressCase));

    renderPage();

    const markButton = await screen.findByRole("button", { name: "Mark In Progress" });
    expect(markButton).toBeEnabled();

    fireEvent.click(markButton);

    await waitFor(() =>
      expect(adminCasesApi.updateAdminCaseStatus).toHaveBeenCalledWith("case-1", "IN_PROGRESS"),
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Mark In Progress" })).toBeDisabled());
    expect(screen.getAllByText("IN_PROGRESS").length).toBeGreaterThan(0);
  });

  it("disables mark in progress outside triage", async () => {
    (casesApi.fetchCaseDetails as unknown as Mock).mockResolvedValue(buildDetailsResponse(inProgressCase));

    renderPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Mark In Progress" })).toBeDisabled());
    expect(screen.getAllByText("IN_PROGRESS").length).toBeGreaterThan(0);
  });

  it("keeps operator actions disabled for cases read-only roles", async () => {
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["NEFT_FINANCE"]),
        read_only: false,
      },
    });

    renderPage();

    const markButton = await screen.findByRole("button", { name: "Mark In Progress" });
    const closeButton = screen.getByRole("button", { name: "Close Case" });

    expect(markButton).toBeDisabled();
    expect(markButton).toHaveAttribute("title", "Requires cases operate capability");
    expect(closeButton).toBeDisabled();
    expect(closeButton).toHaveAttribute("title", "Requires cases operate capability");

    fireEvent.click(markButton);
    expect(adminCasesApi.updateAdminCaseStatus).not.toHaveBeenCalled();
  });

  it("closes case via backend and refreshes details", async () => {
    (casesApi.fetchCaseDetails as unknown as Mock)
      .mockResolvedValueOnce(buildDetailsResponse())
      .mockResolvedValueOnce(buildDetailsResponse(closedCase));

    renderPage();

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

    await waitFor(() =>
      expect(adminCasesApi.closeAdminCase).toHaveBeenCalledWith(
        "case-1",
        expect.objectContaining({ resolution_note: "Resolved after review and mitigation applied." }),
      ),
    );
    await waitFor(() => expect((casesApi.fetchCaseDetails as unknown as Mock).mock.calls.length).toBeGreaterThan(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Close Case" })).toBeDisabled());
    expect(screen.getAllByText("CLOSED").length).toBeGreaterThan(0);
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
            changes: [{ field: "status", from: "TRIAGE", to: "IN_PROGRESS" }],
            export_ref: { kind: "explain_export", id: "exp-1", url: "/v1/admin/exports/exp-1" },
          },
        },
      ],
    });

    renderPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Audit timeline" })).toBeInTheDocument());
    const timeline = screen.getByTestId("audit-timeline");
    expect(within(timeline).getByText("Status changed")).toBeInTheDocument();
    expect(within(timeline).getByText("status")).toBeInTheDocument();
    expect(within(timeline).getByText("IN_PROGRESS")).toBeInTheDocument();
    expect(within(timeline).getByText("Request ID")).toBeInTheDocument();
    expect(within(timeline).getByText("Trace ID")).toBeInTheDocument();
    const exportLink = within(timeline).getByRole("link", { name: "Open export" });
    expect(exportLink).toHaveAttribute("href", "/v1/admin/exports/exp-1");
  });

  it("falls back to synthetic events when unavailable", async () => {
    (adminCasesApi.listCaseEvents as unknown as Mock).mockResolvedValue({ items: [], unavailable: true });

    renderPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Audit timeline" })).toBeInTheDocument());
    const timeline = screen.getByTestId("audit-timeline");
    expect(within(timeline).getByText("Case created")).toBeInTheDocument();
  });
});

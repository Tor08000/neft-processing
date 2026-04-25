import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";

import ExplainPage from "./ExplainPage";
import * as explainApi from "../api/explainV2";
import * as casesApi from "../api/cases";

vi.mock("../api/explainV2", () => ({
  fetchExplainV2: vi.fn(),
  fetchExplainActions: vi.fn(),
  fetchExplainDiff: vi.fn(),
  evaluateWhatIf: vi.fn(),
}));

vi.mock("../api/cases", () => ({
  createCase: vi.fn(),
}));

vi.mock("../api/adminExports", () => ({
  createCaseExport: vi.fn(),
}));

describe("ExplainPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.localStorage.clear();

    (explainApi.fetchExplainV2 as ReturnType<typeof vi.fn>).mockResolvedValue({
      kind: "operation",
      id: "tx-1",
      decision: "REVIEW",
      score: 0.72,
      score_band: "medium",
      policy_snapshot: "policy-1",
      generated_at: "2026-04-14T09:30:00Z",
      reason_tree: {
        id: "root",
        title: "Root reason",
        weight: 1,
        children: [],
        evidence_refs: [],
      },
      evidence: [],
      documents: [],
      recommended_actions: [
        {
          action_code: "manual_review",
          title: "Manual review",
          description: "Escalate for manual review",
        },
        {
          action_code: "request_docs",
          title: "Request documents",
          description: "Ask for supporting documents",
        },
      ],
    });

    (explainApi.fetchExplainActions as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        action_code: "manual_review",
        label: "Manual review",
        description: "Escalate for manual review",
      },
      {
        action_code: "request_docs",
        label: "Request documents",
        description: "Ask for supporting documents",
      },
    ]);

    (explainApi.evaluateWhatIf as ReturnType<typeof vi.fn>).mockResolvedValue({
      subject: { type: "FUEL_TX", id: "tx-1" },
      candidates: [
        {
          rank: 1,
          action: { code: "manual_review", title: "Manual review" },
          projection: {
            probability_improved_pct: 64,
            expected_effect_label: "Review risk",
            window_days: 7,
          },
          memory: { memory_penalty_pct: 8, cooldown: false },
          risk: { outlook: "reduced", notes: ["manual inspection"] },
          what_if_score: 0.71,
          explain: ["Escalation reduces uncertainty"],
        },
        {
          rank: 2,
          action: { code: "request_docs", title: "Request documents" },
          projection: {
            probability_improved_pct: 52,
            expected_effect_label: "Collect evidence",
            window_days: 7,
          },
          memory: { memory_penalty_pct: 4, cooldown: false },
          risk: { outlook: "stable", notes: ["document proof required"] },
          what_if_score: 0.63,
          explain: ["Additional evidence improves explain quality"],
        },
      ],
    });
  });

  it("opens the shared what-if detail panel from actions mode", async () => {
    render(
      <MemoryRouter initialEntries={["/explain?kind=operation&id=tx-1&mode=actions"]}>
        <Routes>
          <Route path="/explain" element={<ExplainPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Selected actions")).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText(/Manual review/i));
    await userEvent.click(screen.getByLabelText(/Request documents/i));
    await userEvent.click(screen.getByRole("button", { name: "Открыть What-if" }));

    await waitFor(() =>
      expect(explainApi.evaluateWhatIf).toHaveBeenCalledWith({
        subject: { type: "FUEL_TX", id: "tx-1" },
        max_candidates: 2,
      }),
    );

    expect(screen.getByText(/Coverage:/i)).toBeInTheDocument();
    expect(screen.queryByText(/Mastery:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Streak:/i)).not.toBeInTheDocument();
    expect(screen.getByText("What-if сравнение")).toBeInTheDocument();
    expect(screen.getByText("Симуляция (не исполняется)")).toBeInTheDocument();
    expect(await screen.findByText("Эффект: Review risk")).toBeInTheDocument();
    expect(screen.getByText("Эффект: Collect evidence")).toBeInTheDocument();
  });

  it("opens the canonical admin case route after a case is created", async () => {
    (casesApi.createCase as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "case-42",
      tenant_id: 1,
      kind: "operation",
      title: "Manual review",
      status: "TRIAGE",
      queue: "FRAUD_OPS",
      priority: "MEDIUM",
      escalation_level: 0,
      created_at: "2026-04-14T09:35:00Z",
      updated_at: "2026-04-14T09:35:00Z",
      last_activity_at: "2026-04-14T09:35:00Z",
    });

    const CaseRoute = () => {
      const { id } = useParams();
      return <div>Case route {id}</div>;
    };

    render(
      <MemoryRouter initialEntries={["/explain?kind=operation&id=tx-1&mode=case&include_diff=0"]}>
        <Routes>
          <Route path="/explain" element={<ExplainPage />} />
          <Route path="/cases/:id" element={<CaseRoute />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Explain v2")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Создать кейс" }));

    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Создать" }));

    await waitFor(() => expect(casesApi.createCase).toHaveBeenCalled());
    expect(await screen.findByText("ID: case-42")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Открыть кейс" }));

    expect(await screen.findByText("Case route case-42")).toBeInTheDocument();
  });
});

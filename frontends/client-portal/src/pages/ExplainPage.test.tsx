import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const fetchExplainV2Mock = vi.fn();
const fetchExplainDiffMock = vi.fn();

vi.mock("../api/explainV2", () => ({
  fetchExplainV2: (...args: unknown[]) => fetchExplainV2Mock(...args),
  fetchExplainDiff: (...args: unknown[]) => fetchExplainDiffMock(...args),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: {
      token: "test.header.payload",
      email: "client@example.test",
      timezone: "Europe/Moscow",
    },
  }),
}));

vi.mock("../components/Toast/useToast", () => ({
  useToast: () => ({
    toast: null,
    showToast: vi.fn(),
  }),
}));

vi.mock("../components/Toast/Toast", () => ({
  Toast: () => null,
}));

import { ExplainPage } from "./ExplainPage";

const explainPayload = {
  id: "explain-1",
  decision: "APPROVE",
  score: 0.22,
  score_band: "low",
  generated_at: "2026-04-14T12:00:00Z",
  policy_snapshot: "policy-v1",
  reason_tree: {
    id: "reason-root",
    title: "Root reason",
    weight: 0.5,
    evidence_refs: ["ev-1"],
    children: [],
  },
  evidence: [
    {
      id: "ev-1",
      type: "field",
      source: "rule",
      label: "Merchant",
      value: "station-1",
      confidence: 0.9,
    },
  ],
  documents: [],
  recommended_actions: [],
};

describe("ExplainPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    fetchExplainV2Mock.mockResolvedValue(explainPayload);
    fetchExplainDiffMock.mockResolvedValue({
      meta: { left: { label: "Left" }, right: { label: "Right" } },
      decision_diff: { before: "APPROVE", after: "REVIEW" },
      score_diff: { risk_before: 0.1, risk_after: 0.2, delta: 0.1 },
      reasons_diff: [],
      evidence_diff: [],
      action_impact: null,
    });
  });

  it("removes export action from the main explain toolbar", async () => {
    render(
      <MemoryRouter initialEntries={["/explain?kind=operation&id=op-1"]}>
        <Routes>
          <Route path="/explain" element={<ExplainPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Explain v2" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Экспорт" })).not.toBeInTheDocument();
  });

  it("keeps diff mode without a dead export button", async () => {
    render(
      <MemoryRouter initialEntries={["/explain?kind=operation&id=op-1&diff=1&left_snapshot=latest&right_snapshot=previous"]}>
        <Routes>
          <Route path="/explain" element={<ExplainPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Explain Diff" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Экспорт" })).not.toBeInTheDocument();
  });
});

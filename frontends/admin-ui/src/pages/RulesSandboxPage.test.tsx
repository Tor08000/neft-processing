import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RulesSandboxPage from "./RulesSandboxPage";
import * as rulesApi from "../api/unifiedRules";

vi.mock("../api/unifiedRules", () => ({
  fetchRuleSetVersions: vi.fn(),
  evaluateRulesSandbox: vi.fn(),
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RulesSandboxPage />
    </QueryClientProvider>,
  );
}

describe("RulesSandboxPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the empty rule-set state without hiding active-by-scope evaluation", async () => {
    vi.mocked(rulesApi.fetchRuleSetVersions).mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("No rule set versions")).toBeInTheDocument();
    expect(screen.getByText("Active by scope remains available.")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Active by scope" })).toBeInTheDocument();
  });

  it("renders version loading failures as retryable operator state", async () => {
    vi.mocked(rulesApi.fetchRuleSetVersions).mockRejectedValue(new Error("versions down"));

    renderPage();

    expect(await screen.findByText("Rule set versions unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByText("versions down")).toBeInTheDocument();
    expect(screen.getByLabelText("Rule set version")).toBeDisabled();
  });

  it("pins a version and renders a reproducible sandbox decision", async () => {
    vi.mocked(rulesApi.fetchRuleSetVersions).mockResolvedValue([
      {
        id: 7,
        name: "fleet-v1",
        scope: "FLEET",
        status: "ACTIVE",
        created_at: "2026-04-23T00:00:00Z",
      },
    ]);
    vi.mocked(rulesApi.evaluateRulesSandbox).mockResolvedValue({
      version: { rule_set_version_id: 7, scope: "FLEET" },
      matched_rules: [
        {
          code: "RULE_OK",
          policy: "FLEET_DAILY_SPEND",
          priority: 10,
          reason_code: "OK",
          explain: "matched deterministic threshold",
        },
      ],
      decision: "ALLOW",
      reason_codes: ["OK"],
      explain: {
        inputs: { scope: "FLEET" },
        metrics: { AMOUNT: 50000 },
        resolution: { rule_set_version_id: 7 },
      },
    });

    renderPage();

    await screen.findByRole("option", { name: "fleet-v1 (ACTIVE)" });
    await userEvent.selectOptions(screen.getByLabelText("Rule set version"), "7");
    await userEvent.click(screen.getByRole("button", { name: "Evaluate" }));

    await waitFor(() =>
      expect(rulesApi.evaluateRulesSandbox).toHaveBeenCalledWith(
        expect.objectContaining({
          mode: "synthetic",
          scope: "FLEET",
          version_id: 7,
        }),
      ),
    );
    expect(await screen.findByText("ALLOW")).toBeInTheDocument();
    expect(screen.getByText("RULE_OK")).toBeInTheDocument();
    expect(screen.getByText("FLEET / 7")).toBeInTheDocument();
  });

  it("blocks historical evaluation until a transaction id is present", async () => {
    vi.mocked(rulesApi.fetchRuleSetVersions).mockResolvedValue([]);

    renderPage();

    await screen.findByText("No rule set versions");
    await userEvent.selectOptions(screen.getByLabelText("Mode"), "historical");
    expect(screen.getByText("Transaction ID is required for historical mode.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Evaluate" }));

    expect(rulesApi.evaluateRulesSandbox).not.toHaveBeenCalled();
    expect(screen.getByText("Evaluation failed")).toBeInTheDocument();
    expect(screen.getByText("Transaction ID is required for historical evaluation.")).toBeInTheDocument();
  });
});

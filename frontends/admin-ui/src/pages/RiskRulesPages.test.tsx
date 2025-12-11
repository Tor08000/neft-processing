import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RiskRulesListPage } from "./RiskRulesListPage";
import { RiskRuleDetailsPage } from "./RiskRuleDetailsPage";
import { type RiskRuleListResponse, type RiskRule } from "../types/riskRules";

function renderWithProviders(element: React.ReactElement, initialEntries = ["/"]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={initialEntries}>{element}</MemoryRouter>
    </QueryClientProvider>,
  );
}

const mockRule = (id: number, name: string, action: string): RiskRule => ({
  id,
  description: "demo",
  enabled: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  version: 1,
  dsl: {
    name,
    scope: "GLOBAL",
    subject_id: null,
    selector: { merchant_ids: null, terminal_ids: null, geo: null, hours: null },
    window: null,
    metric: "always",
    value: 1,
    action: action as RiskRule["dsl"]["action"],
    priority: 10,
    enabled: true,
    reason: "demo",
  },
});

describe("Risk rules pages", () => {
  it("renders rules list", async () => {
    const payload: RiskRuleListResponse = { items: [mockRule(1, "rule-1", "LOW")], total: 1, limit: 20, offset: 0 };
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } }),
    ) as unknown as typeof fetch;

    renderWithProviders(<RiskRulesListPage />);

    await waitFor(() => expect(screen.getByText("rule-1")).toBeInTheDocument());
    expect(screen.getByText("LOW")).toBeInTheDocument();
  });

  it("updates rule from details", async () => {
    const rule = mockRule(42, "rule-42", "LOW");
    const updated = { ...rule, dsl: { ...rule.dsl, action: "HIGH" as const } };

    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      if (url.includes("/api/v1/admin/risk/rules/42") && (!init || init.method === "GET")) {
        return Promise.resolve(
          new Response(JSON.stringify(rule), { status: 200, headers: { "Content-Type": "application/json" } }),
        );
      }
      if (init?.method === "PUT") {
        return Promise.resolve(
          new Response(JSON.stringify(updated), { status: 200, headers: { "Content-Type": "application/json" } }),
        );
      }
      return Promise.reject(new Error("Unexpected call"));
    });

    global.fetch = fetchMock as unknown as typeof fetch;

    renderWithProviders(
      <Routes>
        <Route path="/risk/rules/:id" element={<RiskRuleDetailsPage />} />
      </Routes>,
      ["/risk/rules/42"],
    );

    await waitFor(() => expect(screen.getByDisplayValue("rule-42")).toBeInTheDocument());

    await userEvent.selectOptions(screen.getByLabelText(/Action/i), "HIGH");
    await userEvent.click(screen.getByText("Сохранить"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/admin/risk/rules/42"),
      expect.objectContaining({ method: "PUT" }),
    ));
    expect(screen.getByDisplayValue("HIGH")).toBeInTheDocument();
  });
});

import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import RevenuePage from "./RevenuePage";
import * as revenueApi from "../../api/revenue";

vi.mock("../../api/revenue", () => ({
  fetchRevenueSummary: vi.fn(),
  fetchOverdueList: vi.fn(),
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    accessToken: "token-1",
  }),
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RevenuePage />
    </QueryClientProvider>,
  );
}

describe("RevenuePage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders extracted empty-state copy for overdue and mix tables", async () => {
    (revenueApi.fetchRevenueSummary as ReturnType<typeof vi.fn>).mockResolvedValue({
      as_of: "2026-04-15",
      mrr: { amount: 100000, currency: "RUB" },
      arr: { amount: 1200000, currency: "RUB" },
      active_orgs: 4,
      overdue_orgs: 0,
      overdue_amount: 0,
      usage_revenue_mtd: 0,
      plan_mix: [],
      addon_mix: [],
      overdue_buckets: [
        { bucket: "all", label: "All", orgs: 0, amount: 0 },
        { bucket: "0_7", label: "0-7", orgs: 0, amount: 0 },
      ],
    });
    (revenueApi.fetchOverdueList as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });

    renderPage();

    expect(await screen.findByText("Revenue")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Все" })).toBeInTheDocument();
    expect(await screen.findByText("Нет просрочек")).toBeInTheDocument();
    expect(screen.getByText("Нет планов")).toBeInTheDocument();
    expect(screen.getByText("Нет add-ons")).toBeInTheDocument();
  });
});

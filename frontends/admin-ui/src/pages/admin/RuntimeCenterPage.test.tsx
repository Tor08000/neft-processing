import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import RuntimeCenterPage from "./RuntimeCenterPage";
import * as runtimeApi from "../../api/runtimeSummary";
import { runtimeCenterCopy } from "./runtimeStatusCopy";

const useAuthMock = vi.fn();
const useAdminMock = vi.fn();

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../../admin/AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

vi.mock("../../api/runtimeSummary", () => ({
  fetchRuntimeSummary: vi.fn(),
}));

vi.mock("../../components/CopyButton/CopyButton", () => ({
  CopyButton: ({ label }: { label: string }) => <button type="button">{label}</button>,
}));

const renderPage = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RuntimeCenterPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("RuntimeCenterPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "token" });
    useAdminMock.mockReturnValue({ profile: { env: { name: "dev" }, read_only: false } });
  });

  it("renders grounded drilldowns and degraded evidence from canonical runtime summary", async () => {
    vi.mocked(runtimeApi.fetchRuntimeSummary).mockResolvedValue({
      ts: "2026-04-13T10:00:00Z",
      environment: "prod",
      read_only: false,
      health: {
        core_api: "UP",
        auth_host: "UP",
        gateway: "UP",
        integration_hub: "DEGRADED",
        document_service: "UP",
        logistics_service: "UP",
        ai_service: "UP",
        postgres: "DEGRADED",
        redis: "UP",
        minio: "UP",
        clickhouse: "UP",
        prometheus: "DOWN",
        grafana: "UP",
        loki: "UP",
        otel_collector: "UP",
      },
      queues: {
        settlement: { depth: 2, oldest_age_sec: 18 },
        payout: { depth: 1, oldest_age_sec: 9 },
        blocked_payouts: { count: 3 },
        payment_intakes_pending: { count: 4 },
      },
      violations: {
        immutable: { count: 0, top: [] },
        invariants: { count: 1, top: ["ledger_gap"] },
        sla_penalties: { count: 2, top: ["support_breach"] },
      },
      money_risk: {
        payouts_blocked: 3,
        settlements_pending: 2,
        overdue_clients: 1,
      },
      events: {
        critical_last_10: [
          {
            ts: "2026-04-13T09:55:00Z",
            kind: "runtime.alert",
            message: "Critical payout backlog",
            correlation_id: "corr-123",
          },
        ],
      },
      warnings: ["missing_table:audit_log"],
      missing_tables: ["audit_log"],
      external_providers: [
        {
          service: "integration-hub",
          provider: "diadok",
          mode: "sandbox",
          status: "DEGRADED",
          configured: false,
          last_error_code: "diadok_not_configured",
          message: "DIADOK requires base URL and API token before provider smoke can pass",
        },
      ],
    });

    renderPage();

    expect(await screen.findByRole("link", { name: "Escalations inbox" })).toHaveAttribute("href", "/ops/escalations");
    expect(screen.getByRole("link", { name: "Blocked payouts" })).toHaveAttribute("href", "/ops/payouts/blocked");
    expect(screen.getByText("missing_table:audit_log")).toBeInTheDocument();
    expect(screen.getByText("audit_log")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open audit" })).toHaveAttribute("href", "/audit/corr-123");
    expect(screen.getByRole("heading", { name: "integration hub" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "prometheus" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "External provider diagnostics" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "diadok" })).toBeInTheDocument();
    expect(screen.getByText("last error: diadok_not_configured")).toBeInTheDocument();
  });

  it("renders honest empty states when queues, violations and critical events are absent", async () => {
    vi.mocked(runtimeApi.fetchRuntimeSummary).mockResolvedValue({
      ts: "2026-04-13T10:00:00Z",
      environment: "dev",
      read_only: true,
      health: {
        core_api: "UP",
        auth_host: "UP",
        gateway: "UP",
        integration_hub: "UP",
        document_service: "UP",
        logistics_service: "UP",
        ai_service: "UP",
        postgres: "UP",
        redis: "UP",
        minio: "UP",
        clickhouse: "UP",
        prometheus: "UP",
        grafana: "UP",
        loki: "UP",
        otel_collector: "UP",
      },
      queues: {
        settlement: { depth: 0, oldest_age_sec: 0 },
        payout: { depth: 0, oldest_age_sec: 0 },
        blocked_payouts: { count: 0 },
        payment_intakes_pending: { count: 0 },
      },
      violations: {
        immutable: { count: 0, top: [] },
        invariants: { count: 0, top: [] },
        sla_penalties: { count: 0, top: [] },
      },
      money_risk: {
        payouts_blocked: 0,
        settlements_pending: 0,
        overdue_clients: 0,
      },
      events: {
        critical_last_10: [],
      },
      warnings: [],
      missing_tables: [],
      external_providers: [],
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: runtimeCenterCopy.queues.emptyTitle })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: runtimeCenterCopy.violations.emptyTitle })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: runtimeCenterCopy.events.emptyTitle })).toBeInTheDocument();
  });

  it("marks missing observed health keys as degraded instead of silently green", async () => {
    vi.mocked(runtimeApi.fetchRuntimeSummary).mockResolvedValue({
      ts: "2026-04-13T10:00:00Z",
      environment: "dev",
      read_only: false,
      health: {
        core_api: "UP",
        auth_host: "UP",
        gateway: "UP",
      } as never,
      queues: {
        settlement: { depth: 0, oldest_age_sec: 0 },
        payout: { depth: 0, oldest_age_sec: 0 },
        blocked_payouts: { count: 0 },
        payment_intakes_pending: { count: 0 },
      },
      violations: {
        immutable: { count: 0, top: [] },
        invariants: { count: 0, top: [] },
        sla_penalties: { count: 0, top: [] },
      },
      money_risk: {
        payouts_blocked: 0,
        settlements_pending: 0,
        overdue_clients: 0,
      },
      events: {
        critical_last_10: [],
      },
      warnings: [],
      missing_tables: [],
      external_providers: [],
    });

    renderPage();

    const prometheusHeading = await screen.findByRole("heading", { name: "prometheus" });
    const prometheusCard = prometheusHeading.closest("section");
    expect(prometheusCard).not.toBeNull();
    expect(within(prometheusCard as HTMLElement).getByText("DEGRADED")).toBeInTheDocument();
  });
});

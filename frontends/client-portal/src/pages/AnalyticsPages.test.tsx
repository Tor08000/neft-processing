import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import { AnalyticsDashboardPage } from "./AnalyticsDashboardPage";
import { AnalyticsDeclinesPage } from "./AnalyticsDeclinesPage";
import { AnalyticsExportsPage } from "./AnalyticsExportsPage";
import { AnalyticsMarketplacePage } from "./AnalyticsMarketplacePage";
import { AnalyticsSpendPage } from "./AnalyticsSpendPage";

const ownerSession: AuthSession = {
  token: "test.analytics.owner",
  email: "owner@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const userSession: AuthSession = {
  token: "test.analytics.user",
  email: "user@demo.test",
  roles: ["CLIENT_USER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const dailyMetricsPayload = {
  from: "2024-03-01",
  to: "2024-03-31",
  currency: "RUB",
  spend: {
    total: 120000,
    series: [
      { date: "2024-03-01", value: 20000 },
      { date: "2024-03-02", value: 25000 },
    ],
  },
  orders: {
    total: 80,
    completed: 72,
    refunds: 4,
    series: [
      { date: "2024-03-01", value: 40 },
      { date: "2024-03-02", value: 40 },
    ],
  },
  declines: {
    total: 12,
    top_reason: "LIMIT",
    series: [
      { date: "2024-03-01", value: 6 },
      { date: "2024-03-02", value: 6 },
    ],
  },
  documents: {
    attention: 3,
  },
  exports: {
    attention: 1,
  },
  attention: [
    {
      id: "attention-1",
      title: "3 документа ждут подписи",
      description: "Перейдите в документы для подписи",
      href: "/documents?requiresAction=yes",
      severity: "warning",
    },
  ],
};

const declinesPayload = {
  total: 10,
  top_reasons: [
    { reason: "LIMIT", count: 6 },
    { reason: "RISK", count: 4 },
  ],
  trend: [
    { date: "2024-03-01", reason: "LIMIT", count: 3 },
    { date: "2024-03-02", reason: "RISK", count: 2 },
  ],
  expensive: [
    { id: "decline-1", reason: "LIMIT", amount: 5000, station: "АЗС-1" },
  ],
  heatmap: [],
};

const documentsSummaryPayload = {
  issued: 12,
  signed: 9,
  edo_pending: 2,
  edo_failed: 1,
  attention: [],
};

const exportsSummaryPayload = {
  total: 4,
  ok: 3,
  mismatch: 1,
  items: [
    {
      id: "export-1",
      status: "OK",
      checksum: "123",
      mapping_version: "v2",
      created_at: "2024-03-10T10:00:00Z",
    },
  ],
};

const spendSummaryPayload = {
  currency: "RUB",
  total_spend: 0,
  avg_daily_spend: 0,
  trend: [],
  top_stations: [],
  top_merchants: [],
  top_cards: [],
  top_drivers: [],
  product_breakdown: [],
  export_available: false,
  export_dataset: "spend",
};

const ordersSummaryPayload = {
  total: 0,
  completed: 0,
  cancelled: 0,
  refunds_rate: 0,
  refunds_count: 0,
  avg_order_value: 0,
  top_services: [],
  status_breakdown: [],
};

const explainInsightsPayload = {
  from: "2024-03-01",
  to: "2024-03-31",
  top_primary_reasons: [],
  trend: [],
  top_decline_reasons: [],
  top_decline_stations: [],
};

describe("Analytics pages", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  const renderAnalyticsPage = (initialEntry: string, session: AuthSession, page: JSX.Element) =>
    render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={session}>{page}</AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

  it("renders analytics dashboard with attention link", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/bi/metrics/daily")) {
        return Promise.resolve(new Response(JSON.stringify(dailyMetricsPayload), { status: 200 }));
      }
      if (url.includes("/bi/declines")) {
        return Promise.resolve(new Response(JSON.stringify(declinesPayload), { status: 200 }));
      }
      if (url.includes("/bi/documents/summary")) {
        return Promise.resolve(new Response(JSON.stringify(documentsSummaryPayload), { status: 200 }));
      }
      if (url.includes("/bi/exports/summary")) {
        return Promise.resolve(new Response(JSON.stringify(exportsSummaryPayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderAnalyticsPage("/analytics", ownerSession, <AnalyticsDashboardPage />);

    expect(await screen.findByText(/CFO-дешборд/i)).toBeInTheDocument();
    const attentionLink = await screen.findByRole("link", { name: /3 документа ждут подписи/i });
    expect(attentionLink).toHaveAttribute("href", "/documents?requiresAction=yes");
  });

  it("shows production empty state when declines data is missing", async () => {
    const emptyDeclinesPayload = {
      total: 0,
      top_reasons: [],
      trend: [],
      expensive: [],
      heatmap: [],
    };
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/bi/declines")) {
        return Promise.resolve(new Response(JSON.stringify(emptyDeclinesPayload), { status: 200 }));
      }
      if (url.includes("/explain/insights")) {
        return Promise.resolve(new Response(JSON.stringify(explainInsightsPayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderAnalyticsPage("/analytics/declines", ownerSession, <AnalyticsDeclinesPage />);

    expect(await screen.findByText(/Недостаточно данных за выбранный период/i)).toBeInTheDocument();
    expect(screen.queryByText(/Данные в демо появятся позже/i)).not.toBeInTheDocument();
  });

  it("uses demo analytics fallback only when demo mode is explicit", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/bi/declines")) {
        return Promise.resolve(new Response(JSON.stringify({ detail: "not found" }), { status: 404 }));
      }
      if (url.includes("/explain/insights")) {
        return Promise.resolve(new Response(JSON.stringify(explainInsightsPayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderAnalyticsPage("/analytics/declines", ownerSession, <AnalyticsDeclinesPage />);

    expect(await screen.findByText(/Данные в демо появятся позже/i)).toBeInTheDocument();
  });

  it("restricts exports analytics for client users", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/bi/exports/summary")) {
        return Promise.resolve(new Response(JSON.stringify(exportsSummaryPayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderAnalyticsPage("/analytics/exports", userSession, <AnalyticsExportsPage />);

    expect(await screen.findByText(/Финансовая аналитика доступна/i)).toBeInTheDocument();
  });

  it("renders spend analytics production empty state", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/bi/spend/summary")) {
        return Promise.resolve(new Response(JSON.stringify(spendSummaryPayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderAnalyticsPage("/analytics/spend", ownerSession, <AnalyticsSpendPage />);

    expect(await screen.findByText(/Недостаточно данных за выбранный период/i)).toBeInTheDocument();
    expect(screen.queryByText(/Данные в демо появятся позже/i)).not.toBeInTheDocument();
  });

  it("renders marketplace analytics empty state", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/bi/orders/summary")) {
        return Promise.resolve(new Response(JSON.stringify(ordersSummaryPayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    renderAnalyticsPage("/analytics/marketplace", ownerSession, <AnalyticsMarketplacePage />);

    const emptyStates = await screen.findAllByText(/Недостаточно данных за выбранный период/i);
    expect(emptyStates.length).toBeGreaterThan(0);
  });
});

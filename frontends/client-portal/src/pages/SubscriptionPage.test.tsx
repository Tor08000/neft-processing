import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SubscriptionPage } from "./SubscriptionPage";

const useAuthMock = vi.fn();
const useClientMock = vi.fn();
const fetchMySubscriptionMock = vi.fn();
const fetchSubscriptionBenefitsMock = vi.fn();
const fetchGamificationSummaryMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => useClientMock(),
}));

vi.mock("../api/subscriptions", () => ({
  fetchMySubscription: (...args: unknown[]) => fetchMySubscriptionMock(...args),
  fetchSubscriptionBenefits: (...args: unknown[]) => fetchSubscriptionBenefitsMock(...args),
  fetchGamificationSummary: (...args: unknown[]) => fetchGamificationSummaryMock(...args),
}));

describe("SubscriptionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({ user: { token: "test.header.payload" } });
    fetchMySubscriptionMock.mockResolvedValue({
      id: "sub-1",
      tenant_id: 1,
      client_id: "client-1",
      plan_id: "CLIENT_START",
      status: "ACTIVE",
      start_at: "2026-04-01T00:00:00Z",
      end_at: "2026-05-01T00:00:00Z",
      auto_renew: true,
      plan: { code: "CLIENT_START", title: "Client Start" },
    });
    fetchSubscriptionBenefitsMock.mockResolvedValue({
      plan: { code: "CLIENT_START", title: "Client Start" },
      modules: [{ module_code: "MARKETPLACE", enabled: true }],
      unavailable_modules: [{ module_code: "ANALYTICS", enabled: false }],
    });
    fetchGamificationSummaryMock.mockResolvedValue({
      as_of: "2026-04-13T10:00:00Z",
      plan_code: "CLIENT_START",
      bonuses: [{ title: "Скидка на сервис" }],
      streaks: [],
      achievements: [{ title: "Первый заказ" }],
    });
  });

  it("renders honest subscription summary for an individual client", async () => {
    useClientMock.mockReturnValue({
      client: {
        org: { id: "org-1", org_type: "INDIVIDUAL" },
        subscription: { plan_code: "CLIENT_START", support_plan: "standard" },
      },
    });

    render(
      <MemoryRouter>
        <SubscriptionPage />
      </MemoryRouter>,
    );

    expect(await screen.findAllByText("Client Start")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Подписка и тариф" })).toBeInTheDocument();
    expect(screen.getByText("INDIVIDUAL")).toBeInTheDocument();
    expect(screen.getAllByText("STANDARD").length).toBeGreaterThan(0);
    expect(screen.getByText("Маркетплейс")).toBeInTheDocument();
    expect(screen.getByText("Аналитика")).toBeInTheDocument();
    expect(screen.getByText("Скидка на сервис")).toBeInTheDocument();
    expect(screen.getByText("Программа активности")).toBeInTheDocument();
    expect(
      screen.getByText(/Портал показывает, какие бонусы и механики поддерживает ваш тариф/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Client Portal — Тарифы и возможности/i)).not.toBeInTheDocument();
  });

  it("renders business workspace context and tariff change CTA", async () => {
    useClientMock.mockReturnValue({
      client: {
        org: { id: "org-1", org_type: "LEGAL" },
        subscription: { plan_code: "CLIENT_BUSINESS", support_plan: "priority" },
      },
    });

    render(
      <MemoryRouter>
        <SubscriptionPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Доступные планы")).toBeInTheDocument();
    expect(screen.getByText("BUSINESS")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Запросить изменение тарифа" })).toHaveAttribute(
      "href",
      "/client/support/new?topic=subscription_change",
    );
  });

  it("renders upgrade preview honestly for free-trial clients", async () => {
    useClientMock.mockReturnValue({
      client: {
        org: { id: "org-1", org_type: "INDIVIDUAL" },
        subscription: { plan_code: "CLIENT_FREE_TRIAL", support_plan: "community" },
      },
    });
    fetchMySubscriptionMock.mockResolvedValue({
      id: "sub-free",
      tenant_id: 1,
      client_id: "client-1",
      plan_id: "CLIENT_FREE_TRIAL",
      status: "FREE",
      start_at: "2026-04-01T00:00:00Z",
      end_at: null,
      auto_renew: false,
      plan: { code: "CLIENT_FREE_TRIAL", title: "Client Free Trial" },
    });
    fetchSubscriptionBenefitsMock.mockResolvedValue({
      plan: { code: "CLIENT_FREE_TRIAL", title: "Client Free Trial" },
      modules: [{ module_code: "DOCUMENTS", enabled: true }],
      unavailable_modules: [{ module_code: "ANALYTICS", enabled: false }],
    });
    fetchGamificationSummaryMock.mockResolvedValue({
      as_of: "2026-04-13T10:00:00Z",
      plan_code: "CLIENT_FREE_TRIAL",
      bonuses: [],
      streaks: [],
      achievements: [],
      preview: {
        plan_title: "Client Start",
        modules: [{ module_code: "MARKETPLACE", enabled: true }],
        available: {
          achievements: [{ title: "Первый заказ" }],
          bonuses: [{ title: "Скидка на сервис" }],
          streaks: [{ title: "3 недели без просрочек" }],
        },
      },
    });

    render(
      <MemoryRouter>
        <SubscriptionPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Что откроется после апгрейда")).toBeInTheDocument();
    expect(screen.getByText("Client Start")).toBeInTheDocument();
    expect(screen.getByText("3 недели без просрочек")).toBeInTheDocument();
    expect(screen.queryByText("Пока нет достижений.")).not.toBeInTheDocument();
  });
});

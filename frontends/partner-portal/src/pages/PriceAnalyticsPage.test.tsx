import { render, screen, waitFor, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { PortalProvider } from "../auth/PortalContext";
import type { AuthSession, PortalMeResponse } from "../api/types";
import i18n from "../i18n";
import { AnalyticsPageProd } from "./analytics/AnalyticsPageProd";

const session: AuthSession = {
  token: "token-analytics",
  email: "owner@neft.local",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

const portalMe: PortalMeResponse = {
  user: {
    id: "user-1",
    email: session.email,
    subject_type: session.subjectType,
  },
  org_roles: ["PARTNER"],
  user_roles: ["PARTNER_OWNER"],
  capabilities: ["PARTNER_PRICING", "PARTNER_ANALYTICS"],
  access_state: "ACTIVE",
  gating: {
    onboarding_enabled: false,
    legal_gate_enabled: false,
  },
  partner: {
    kind: "MARKETPLACE_PARTNER",
    partner_role: "OWNER",
    partner_roles: ["OWNER"],
    default_route: "/prices/analytics",
    workspaces: [
      { code: "marketplace", label: "Marketplace", default_route: "/products" },
      { code: "support", label: "Support", default_route: "/support/requests" },
      { code: "profile", label: "Profile", default_route: "/partner/profile" },
    ],
  },
};

let portalPayload: PortalMeResponse = portalMe;

const mockFetch = (url: string) => {
  if (url.includes("/partner/auth/verify")) {
    return jsonResponse({ ok: true });
  }
  if (url.includes("/portal/me")) {
    return jsonResponse(portalPayload);
  }
  if (url.includes("/partner/prices/analytics/versions/series")) {
    return jsonResponse([
      { date: "2024-03-01", orders_count: 10, revenue_total: 20000 },
      { date: "2024-03-02", orders_count: 12, revenue_total: 22000 },
    ]);
  }
  if (url.includes("/partner/prices/analytics/versions")) {
    return jsonResponse([
      {
        price_version_id: "version-1",
        published_at: "2024-03-01T00:00:00Z",
        orders_count: 22,
        revenue_total: 42000,
        avg_order_value: 1909,
        refunds_count: 1,
      },
      {
        price_version_id: "version-0",
        published_at: "2024-02-15T00:00:00Z",
        orders_count: 30,
        revenue_total: 50000,
        avg_order_value: 1666,
        refunds_count: 2,
      },
    ]);
  }
  if (url.includes("/partner/prices/analytics/offers")) {
    return jsonResponse([
      {
        offer_id: "offer-1",
        orders_count: 12,
        conversion_rate: 0.18,
        avg_price: 1200,
        revenue_total: 14400,
      },
    ]);
  }
  if (url.includes("/partner/prices/analytics/insights")) {
    return jsonResponse([
      {
        type: "PRICE_INCREASE_EFFECT",
        severity: "INFO",
        message: "После публикации версии version-1 количество заказов снизилось на 12% за 7 дней.",
        price_version_id: "version-1",
      },
    ]);
  }
  return jsonResponse([]);
};

const renderPage = (initialSession: AuthSession = session) =>
  render(
    <I18nextProvider i18n={i18n}>
      <AuthProvider initialSession={initialSession}>
        <PortalProvider>
          <MemoryRouter initialEntries={["/prices/analytics"]}>
            <AnalyticsPageProd />
          </MemoryRouter>
        </PortalProvider>
      </AuthProvider>
    </I18nextProvider>,
  );

beforeEach(() => {
  portalPayload = portalMe;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Price analytics page", () => {
  it("renders analytics content", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Аналитика цен" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Офферы" })).toBeInTheDocument();
      expect(screen.getByText("offer-1")).toBeInTheDocument();
      expect(screen.getByText("После публикации версии version-1 количество заказов снизилось на 12% за 7 дней.")).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it("renders empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(jsonResponse([]))) as unknown as typeof fetch,
    );

    renderPage();

    expect(await screen.findByText("Пока недостаточно данных для аналитики.")).toBeInTheDocument();
  });

  it("maps API response into tables", async () => {
    renderPage();

    await waitFor(() => {
      const versionsSection = screen.getByRole("heading", { name: "Сравнение версий" }).closest("section");
      const offersSection = screen.getByRole("heading", { name: "Офферы" }).closest("section");
      const insightsSection = screen.getByRole("heading", { name: "Инсайты" }).closest("section");

      expect(versionsSection).not.toBeNull();
      expect(offersSection).not.toBeNull();
      expect(insightsSection).not.toBeNull();
      expect(within(versionsSection as HTMLElement).getAllByText("version-0").length).toBeGreaterThan(0);
      expect(within(offersSection as HTMLElement).getByText("offer-1")).toBeInTheDocument();
      expect(within(insightsSection as HTMLElement).getByText("После публикации версии version-1 количество заказов снизилось на 12% за 7 дней.")).toBeInTheDocument();
    }, { timeout: 3000 });
  });
});

describe("Price analytics role gating", () => {
  it("denies access for disallowed roles", async () => {
    const limitedSession: AuthSession = {
      ...session,
      roles: ["PARTNER_OPERATOR"],
    };
    portalPayload = {
      ...portalMe,
      user_roles: ["PARTNER_OPERATOR"],
      capabilities: ["PARTNER_PRICING"],
      partner: {
        ...portalMe.partner,
        partner_role: "OPERATOR",
        partner_roles: ["OPERATOR"],
      },
    };

    renderPage(limitedSession);

    expect(await screen.findByText("У вас нет доступа к аналитике цен.")).toBeInTheDocument();
  });
});

import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import { MarketplaceOrderDetailsPage } from "./MarketplaceOrderDetailsPage";
import { MarketplaceProductDetailsPage } from "./MarketplaceProductDetailsPage";

const baseSession: AuthSession = {
  token: "test.header.payload",
  email: "client@example.test",
  roles: ["CLIENT_ADMIN"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const portalPayload = {
  user: { id: "u-1", email: "client@example.test" },
  org: { id: "org-1", name: "ООО Нефт Тест", org_type: "LEGAL", status: "ACTIVE" },
  org_status: "ACTIVE",
  org_roles: ["CLIENT_ADMIN"],
  user_roles: ["CLIENT_ADMIN"],
  capabilities: ["CLIENT_DASHBOARD", "MARKETPLACE"],
  nav_sections: [],
  modules: { analytics: { enabled: true } },
  features: { onboarding_enabled: true, legal_gate_enabled: false },
  dashboard: { widgets: [], role: "OWNER" },
  access_state: "ACTIVE",
};

const productResponse = {
  id: "product-1",
  type: "SERVICE",
  title: "Техническое обслуживание",
  description: "Полный сервис",
  category: "Service",
  price_model: "FIXED",
  price_config: { amount: 12000, currency: "RUB" },
  price_summary: "12 000 ₽",
  partner: { id: "partner-1", company_name: "Партнёр 1", verified: true },
  sla_summary: { obligations: [], penalties: null },
};

const productOffersResponse = {
  items: [
    {
      id: "offer-1",
      subject_type: "SERVICE",
      subject_id: "product-1",
      title: "Приоритетный слот",
      currency: "RUB",
      price_model: "FIXED",
      price_amount: 8900,
      price_min: null,
      price_max: null,
      geo_scope: "ALL_PARTNER_LOCATIONS",
      location_ids: [],
      terms: { min_qty: 1, max_qty: 1 },
      valid_from: null,
      valid_to: null,
    },
  ],
  total: 1,
};

function buildFetchMock() {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input.toString();
    if (url.includes("/portal/me")) {
      return Promise.resolve(new Response(JSON.stringify(portalPayload), { status: 200 }));
    }
    if (url.includes("/client/marketplace/products/product-1/offers")) {
      return Promise.resolve(new Response(JSON.stringify(productOffersResponse), { status: 200 }));
    }
    if (url.includes("/client/marketplace/products/product-1")) {
      return Promise.resolve(new Response(JSON.stringify(productResponse), { status: 200 }));
    }
    if (url.includes("/v1/marketplace/client/orders/order-99/events")) {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            {
              id: "event-1",
              order_id: "order-99",
              event_type: "CREATED",
              actor_type: "client",
              created_at: new Date().toISOString(),
              comment: "Заказ создан клиентом",
            },
          ]),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/v1/marketplace/client/orders/order-99/sla")) {
      return Promise.resolve(new Response(JSON.stringify({ obligations: [] }), { status: 200 }));
    }
    if (url.includes("/v1/marketplace/client/orders/order-99/consequences")) {
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    }
    if (url.includes("/client/billing/invoices")) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    }
    if (url.includes("/client/cases")) {
      return Promise.resolve(new Response(JSON.stringify({ items: [], total: 0, limit: 10 }), { status: 200 }));
    }
    if (url.includes("/v1/marketplace/client/orders/order-99")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            id: "order-99",
            status: "CREATED",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            total_amount: 8900,
            currency: "RUB",
            lines: [{ id: "line-1", title_snapshot: "Выездная диагностика" }],
          }),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/v1/marketplace/client/orders") && init?.method === "POST") {
      return Promise.resolve(new Response(JSON.stringify({ id: "order-99", status: "CREATED" }), { status: 200 }));
    }
    if (url.includes("/v1/marketplace/client/events")) {
      return Promise.resolve(new Response(JSON.stringify({ accepted: 1, rejected: 0 }), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
  });
}

describe("Marketplace product details page", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders backend-backed detail fields and SLA fallback", async () => {
    vi.stubGlobal("fetch", buildFetchMock() as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/products/product-1"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={baseSession}>
            <Routes>
              <Route path="/marketplace/products/:productId" element={<MarketplaceProductDetailsPage />} />
              <Route path="/marketplace/orders/:orderId" element={<MarketplaceOrderDetailsPage />} />
            </Routes>
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Техническое обслуживание")).toBeInTheDocument();
    expect(screen.getByText("Партнёр 1")).toBeInTheDocument();
    expect(screen.getByText("12 000 ₽")).toBeInTheDocument();
    expect(screen.getByText("Уровень сервиса")).toBeInTheDocument();
    expect(screen.getByText("SLA будет предоставлен при подтверждении заказа.")).toBeInTheDocument();
  });

  it("hides order button for client user", async () => {
    vi.stubGlobal("fetch", buildFetchMock() as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/products/product-1"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={{ ...baseSession, roles: ["CLIENT_USER"] }}>
            <Routes>
              <Route path="/marketplace/products/:productId" element={<MarketplaceProductDetailsPage />} />
              <Route path="/marketplace/orders/:orderId" element={<MarketplaceOrderDetailsPage />} />
            </Routes>
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Техническое обслуживание")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Заказать" })).not.toBeInTheDocument();
  });

  it("shows order button for client admin", async () => {
    vi.stubGlobal("fetch", buildFetchMock() as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/products/product-1"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={baseSession}>
            <Routes>
              <Route path="/marketplace/products/:productId" element={<MarketplaceProductDetailsPage />} />
              <Route path="/marketplace/orders/:orderId" element={<MarketplaceOrderDetailsPage />} />
            </Routes>
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "Заказать" })).toBeInTheDocument();
  });

  it("opens real order modal and redirects to created order details", async () => {
    vi.stubGlobal("fetch", buildFetchMock() as unknown as typeof fetch);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <MemoryRouter initialEntries={["/marketplace/products/product-1"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={baseSession}>
            <Routes>
              <Route path="/marketplace/products/:productId" element={<MarketplaceProductDetailsPage />} />
              <Route path="/marketplace/orders/:orderId" element={<MarketplaceOrderDetailsPage />} />
            </Routes>
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Заказать" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Детали оффера")).toBeInTheDocument();
    expect(within(dialog).getByDisplayValue(/Приоритетный слот/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Оформить заказ" }));

    expect(await screen.findByText("Заказ создан клиентом")).toBeInTheDocument();
  });
});

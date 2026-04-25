import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider, translate } from "../i18n";
import { MarketplaceOrderDetailsPage } from "./MarketplaceOrderDetailsPage";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_ADMIN"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const PRODUCT_TITLE = "Car wash";
const INCIDENT_TITLE = "Partner delayed confirmation";

const getDetailsTabs = () => Array.from(document.querySelectorAll(".tabs button")) as HTMLButtonElement[];
const tr = (key: string) => translate(key, undefined, "ru");

const mockFetch = (status: string) => (url: string) => {
  if (url.includes("/v1/marketplace/client/orders/order-1/events")) {
    return new Response(
      JSON.stringify([
        {
          id: "event-1",
          order_id: "order-1",
          event_type: "CREATED",
          actor_type: "client",
          created_at: new Date().toISOString(),
          comment: "Order created by client",
        },
      ]),
      { status: 200 },
    );
  }
  if (url.includes("/client/marketplace/orders/order-1/sla")) {
    return new Response(JSON.stringify({ items: [] }), { status: 200 });
  }
  if (url.includes("/client/marketplace/orders/order-1/consequences")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "consequence-1",
            order_id: "order-1",
            evaluation_id: "evaluation-1",
            consequence_type: "CREDIT_NOTE",
            amount: 500,
            currency: "RUB",
            status: "APPLIED",
            created_at: new Date().toISOString(),
          },
        ],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/v1/marketplace/client/orders/order-1/incidents")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "case-1",
            tenant_id: 1,
            kind: "order",
            entity_id: "order-1",
            title: INCIDENT_TITLE,
            status: "TRIAGE",
            queue: "GENERAL",
            priority: "MEDIUM",
            escalation_level: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            last_activity_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 10,
        next_cursor: null,
      }),
      { status: 200 },
    );
  }
  if (url.includes("/v1/marketplace/client/orders/order-1")) {
    return new Response(
      JSON.stringify({
        id: "order-1",
        status,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        total_amount: 1000,
        currency: "RUB",
        lines: [
          {
            id: "line-1",
            title_snapshot: PRODUCT_TITLE,
          },
        ],
      }),
      { status: 200 },
    );
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200 });
};

const mockFetchWithSlaNotFound = (status: string) => (url: string) => {
  if (url.includes("/client/marketplace/orders/order-1/sla")) {
    return new Response(JSON.stringify({ detail: "order_sla_not_found" }), { status: 404 });
  }
  if (url.includes("/client/marketplace/orders/order-1/consequences")) {
    return new Response(JSON.stringify({ items: [] }), { status: 200 });
  }
  return mockFetch(status)(url);
};

const renderMarketplaceOrderPage = () =>
  render(
    <MemoryRouter initialEntries={["/marketplace/orders/order-1"]}>
      <I18nProvider locale="ru">
        <AuthProvider initialSession={session}>
          <Routes>
            <Route path="/marketplace/orders/:orderId" element={<MarketplaceOrderDetailsPage />} />
          </Routes>
        </AuthProvider>
      </I18nProvider>
    </MemoryRouter>,
  );

describe("MarketplaceOrderDetailsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders backend-owned detail label and cancel CTA for created orders", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => Promise.resolve(mockFetch("CREATED")(String(input)))) as unknown as typeof fetch,
    );

    renderMarketplaceOrderPage();

    expect(await screen.findByText(PRODUCT_TITLE)).toBeInTheDocument();
    expect(await screen.findByText(tr("statuses.orders.CREATED"), { selector: ".neft-chip" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: tr("actions.cancel") })).toBeInTheDocument();
  });

  it("renders backend-owned detail label and cancel CTA for pending-payment orders", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) =>
        Promise.resolve(mockFetch("PENDING_PAYMENT")(String(input))),
      ) as unknown as typeof fetch,
    );

    renderMarketplaceOrderPage();

    expect(await screen.findByText(PRODUCT_TITLE)).toBeInTheDocument();
    expect(await screen.findByText(tr("statuses.orders.PENDING_PAYMENT"), { selector: ".neft-chip" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: tr("actions.cancel") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: tr("marketplaceOrderDetails.actions.pay") })).toBeInTheDocument();
  });

  it("renders incidents from the order-scoped marketplace contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => Promise.resolve(mockFetch("CREATED")(String(input)))) as unknown as typeof fetch,
    );

    renderMarketplaceOrderPage();

    expect(await screen.findByText(PRODUCT_TITLE)).toBeInTheDocument();
    fireEvent.click(getDetailsTabs()[2]);
    expect(await screen.findByText(INCIDENT_TITLE)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: tr("common.open") })).toHaveAttribute("href", "/cases/case-1");
  });

  it("shows only grounded credits and penalties in the billing tab", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => Promise.resolve(mockFetch("CREATED")(String(input)))) as unknown as typeof fetch,
    );

    renderMarketplaceOrderPage();

    expect(await screen.findByText(PRODUCT_TITLE)).toBeInTheDocument();
    fireEvent.click(getDetailsTabs()[3]);
    expect(await screen.findByText("CREDIT_NOTE")).toBeInTheDocument();
    expect(screen.getByText("APPLIED")).toBeInTheDocument();
    expect(screen.queryByText("order_sla_consequences_not_found")).not.toBeInTheDocument();
  });

  it("treats missing SLA and consequences as empty owner state, not page error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) =>
        Promise.resolve(mockFetchWithSlaNotFound("CREATED")(String(input))),
      ) as unknown as typeof fetch,
    );

    renderMarketplaceOrderPage();

    expect(await screen.findByText(PRODUCT_TITLE)).toBeInTheDocument();
    fireEvent.click(getDetailsTabs()[1]);
    expect(screen.queryByText("order_sla_not_found")).not.toBeInTheDocument();
    fireEvent.click(getDetailsTabs()[3]);
    expect(screen.queryByText("order_sla_consequences_not_found")).not.toBeInTheDocument();
    expect(
      await screen.findByRole("heading", {
        level: 2,
        name: tr("marketplaceOrderDetails.invoices.emptyTitle"),
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(tr("marketplaceOrderDetails.invoices.emptyDescription"))).toBeInTheDocument();
  });

  it("hides cancel CTA for non-cancelable backend statuses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) =>
        Promise.resolve(mockFetch("CONFIRMED_BY_PARTNER")(String(input))),
      ) as unknown as typeof fetch,
    );

    renderMarketplaceOrderPage();

    expect(await screen.findByText(PRODUCT_TITLE)).toBeInTheDocument();
    expect(await screen.findByText(tr("statuses.orders.CONFIRMED_BY_PARTNER"), { selector: ".neft-chip" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: tr("actions.cancel") })).not.toBeInTheDocument();
  });
});

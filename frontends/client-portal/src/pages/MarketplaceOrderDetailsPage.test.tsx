import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_ADMIN"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const mockFetch = (url: string) => {
  if (url.includes("/v1/marketplace/client/orders/order-1/events")) {
    return new Response(
      JSON.stringify([
        {
          id: "event-1",
          event_type: "CREATED",
          actor_type: "client",
          created_at: new Date().toISOString(),
        },
      ]),
      { status: 200 },
    );
  }
  if (url.includes("/v1/marketplace/client/orders/order-1/sla")) {
    return new Response(JSON.stringify({ obligations: [] }), { status: 200 });
  }
  if (url.includes("/v1/marketplace/client/orders/order-1/consequences")) {
    return new Response(JSON.stringify({ items: [] }), { status: 200 });
  }
  if (url.includes("/client/billing/invoices")) {
    return new Response(JSON.stringify([]), { status: 200 });
  }
  if (url.includes("/client/cases")) {
    return new Response(JSON.stringify({ items: [], total: 0, limit: 10 }), { status: 200 });
  }
  if (url.includes("/v1/marketplace/client/orders/order-1")) {
    return new Response(
      JSON.stringify({
        id: "order-1",
        service_title: "Мойка",
        partner_name: "Партнёр",
        status: "CREATED",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        price_snapshot: { total_amount: 1000, currency: "RUB" },
      }),
      { status: 200 },
    );
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200 });
};

describe("MarketplaceOrderDetailsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders timeline events", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/orders/order-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("CREATED")).toBeInTheDocument();
  });
});

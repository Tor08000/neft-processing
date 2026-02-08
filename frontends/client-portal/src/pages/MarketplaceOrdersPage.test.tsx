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
  if (url.includes("/v1/marketplace/client/orders")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "order-1",
            service_title: "Мойка",
            partner_name: "Партнер",
            status: "CREATED",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            sla_status: "OK",
            price_snapshot: { total_amount: 1000, currency: "RUB" },
          },
          {
            id: "order-2",
            service_title: "Диагностика",
            partner_name: "Партнер",
            status: "COMPLETED",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            sla_status: "OK",
            total_amount: 2000,
            currency: "RUB",
          },
        ],
        total: 2,
      }),
      { status: 200 },
    );
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200 });
};

describe("MarketplaceOrdersPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows cancel action only for created orders", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/orders"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("order-1".slice(0, 8))).toBeInTheDocument();
    const cancelButtons = screen.getAllByRole("button", { name: "Отменить" });
    expect(cancelButtons).toHaveLength(1);
  });
});

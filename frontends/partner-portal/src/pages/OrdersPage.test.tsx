import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "owner@neft.local",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const mockFetch = (url: string) => {
  if (url.includes("/v1/marketplace/partner/orders")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "order-1",
            client_id: "client-1",
            partner_id: "partner-1",
            status: "PAID",
            payment_status: "PAID",
            total_amount: 1000,
            lines: [
              { offer_id: "offer-1", title_snapshot: "Мойка", qty: 1, unit_price: 1000, line_amount: 1000 },
            ],
            sla_response_remaining_seconds: 600,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        page: 1,
        pageSize: 20,
        total: 1,
      }),
      { status: 200 },
    );
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200 });
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("OrdersPage", () => {
  it("renders orders list with SLA timer", async () => {
    render(
      <MemoryRouter initialEntries={["/orders"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("order-1")).toBeInTheDocument();
    expect(screen.getByText("client-1")).toBeInTheDocument();
    expect(screen.getByText("Мойка")).toBeInTheDocument();
    expect(screen.getByText("00:10:00")).toBeInTheDocument();
  });
});

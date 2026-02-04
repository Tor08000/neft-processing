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
  if (url.includes("/partner/orders")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "order-1",
            clientId: "client-1",
            clientName: "Иван",
            partnerId: "partner-1",
            items: [
              { offerId: "offer-1", title: "Мойка", qty: 1, unitPrice: 1000, amount: 1000 },
            ],
            status: "CREATED",
            paymentStatus: "PAID",
            totalAmount: 1000,
            serviceTitle: "Мойка",
            slaResponseRemainingSeconds: 600,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
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
    expect(screen.getByText("Иван")).toBeInTheDocument();
    expect(screen.getByText("Мойка")).toBeInTheDocument();
    expect(screen.getByText("00:10:00")).toBeInTheDocument();
  });
});

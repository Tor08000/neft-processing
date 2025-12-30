import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const dashboardPayload = {
  summary: {
    total_operations: 12,
    total_amount: 245000,
    period: "7 дней",
    active_limits: 2,
    spending_trend: [12000, 18000, 22000, 14000, 30000, 25000, 21000],
    dates: ["2024-03-01", "2024-03-02", "2024-03-03", "2024-03-04", "2024-03-05", "2024-03-06", "2024-03-07"],
  },
  recent_operations: [],
};

const operationsPayload = {
  items: [
    {
      id: "op-1",
      created_at: "2024-03-07T10:00:00Z",
      status: "APPROVED",
      amount: 1200,
      currency: "RUB",
      card_id: "card-1",
      merchant_id: "azs-1",
      product_type: "DIESEL",
      quantity: 20,
    },
  ],
  total: 1,
  limit: 20,
  offset: 0,
};

const explainPayload = {
  primary_reason: "LIMIT",
  secondary_reasons: ["RISK"],
  recommendations: ["Обновить лимиты"],
  actions: [],
  sla: {
    started_at: "2024-03-07T10:00:00Z",
    expires_at: "2024-03-07T12:00:00Z",
    remaining_minutes: 60,
  },
  escalation: { target: "CRM", status: "PENDING" },
};

describe("Client portal pages", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });
  it("renders dashboard without crashing", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/dashboard")) {
        return Promise.resolve(new Response(JSON.stringify(dashboardPayload), { status: 200 }));
      }
      if (url.includes("/operations")) {
        return Promise.resolve(new Response(JSON.stringify(operationsPayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Обзор расходов/i)).toBeInTheDocument();
  });

  it("renders explain view for operation", async () => {
    const fetchMock = vi.fn((input: RequestInfo) =>
      Promise.resolve(
        new Response(
          JSON.stringify(input.toString().includes("/explain") ? explainPayload : { items: [] }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/explain/op-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("LIMIT")).toBeInTheDocument());
  });

  it("renders actions page", () => {
    render(
      <MemoryRouter initialEntries={["/actions"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Actions/i)).toBeInTheDocument();
  });
});

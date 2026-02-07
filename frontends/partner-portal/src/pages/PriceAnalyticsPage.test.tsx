import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-analytics",
  email: "owner@neft.local",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const mockFetch = (url: string) => {
  if (url.includes("/partner/prices/analytics/versions/series")) {
    return new Response(
      JSON.stringify([
        { date: "2024-03-01", orders_count: 10, revenue_total: 20000 },
        { date: "2024-03-02", orders_count: 12, revenue_total: 22000 },
      ]),
      { status: 200 },
    );
  }
  if (url.includes("/partner/prices/analytics/versions")) {
    return new Response(
      JSON.stringify([
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
      ]),
      { status: 200 },
    );
  }
  if (url.includes("/partner/prices/analytics/offers")) {
    return new Response(
      JSON.stringify([
        {
          offer_id: "offer-1",
          orders_count: 12,
          conversion_rate: 0.18,
          avg_price: 1200,
          revenue_total: 14400,
        },
      ]),
      { status: 200 },
    );
  }
  if (url.includes("/partner/prices/analytics/insights")) {
    return new Response(
      JSON.stringify([
        {
          type: "PRICE_INCREASE_EFFECT",
          severity: "INFO",
          message: "После публикации версии version-1 количество заказов снизилось на 12% за 7 дней.",
          price_version_id: "version-1",
        },
      ]),
      { status: 200 },
    );
  }
  return new Response(JSON.stringify([]), { status: 200 });
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Price analytics page", () => {
  it("renders analytics content", async () => {
    render(
      <MemoryRouter initialEntries={["/prices/analytics"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Аналитика цен")).toBeInTheDocument();
    expect(await screen.findByText("version-1")).toBeInTheDocument();
    expect(await screen.findByText("Офферы")).toBeInTheDocument();
  });

  it("renders empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))) as unknown as typeof fetch,
    );

    render(
      <MemoryRouter initialEntries={["/prices/analytics"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Пока недостаточно данных для аналитики.")).toBeInTheDocument();
  });

  it("maps API response into tables", async () => {
    render(
      <MemoryRouter initialEntries={["/prices/analytics"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    const row = await screen.findByText("offer-1");
    expect(row).toBeInTheDocument();
    expect(screen.getByText("version-0")).toBeInTheDocument();
  });
});

describe("Price analytics role gating", () => {
  it("denies access for disallowed roles", async () => {
    const limitedSession: AuthSession = {
      ...session,
      roles: ["PARTNER_OPERATOR"],
    };

    render(
      <MemoryRouter initialEntries={["/prices/analytics"]}>
        <App initialSession={limitedSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("У вас нет доступа к аналитике цен.")).toBeInTheDocument();
  });
});

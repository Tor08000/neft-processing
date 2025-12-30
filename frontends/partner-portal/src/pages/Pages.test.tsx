import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "partner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const mockFetch = (url: string) => {
  if (url.includes("/partner/prices/versions/") && url.includes("/items")) {
    return new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 });
  }
  if (url.includes("/partner/prices/versions/") && url.includes("/audit")) {
    return new Response(JSON.stringify({ items: [] }), { status: 200 });
  }
  if (url.includes("/partner/prices/versions/") && url.includes("/diff")) {
    return new Response(
      JSON.stringify({
        added_count: 0,
        removed_count: 0,
        changed_count: 0,
        sample_changed: [],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/prices/versions/") && !url.endsWith("/versions")) {
    return new Response(
      JSON.stringify({
        id: "version-1",
        partner_id: "partner-1",
        station_scope: "all",
        status: "DRAFT",
        created_at: new Date().toISOString(),
        active: false,
        item_count: 0,
        error_count: 0,
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/prices/versions")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "version-1",
            partner_id: "partner-1",
            station_scope: "all",
            status: "DRAFT",
            created_at: new Date().toISOString(),
            active: false,
            item_count: 0,
            error_count: 0,
          },
        ],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/stations/") && !url.endsWith("/stations")) {
    return new Response(
      JSON.stringify({
        id: "station-1",
        name: "АЗС Север",
        address: "ул. Тестовая, 1",
        status: "active",
        terminals: [],
        declineReasons: [],
        prices: [],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/transactions/") && !url.endsWith("/transactions")) {
    return new Response(
      JSON.stringify({
        id: "tx-1",
        ts: new Date().toISOString(),
        station: "АЗС Север",
        product: "Fuel",
        amount: 1200,
        status: "authorized",
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/settlements/") && !url.endsWith("/settlements")) {
    return new Response(
      JSON.stringify({
        id: "set-1",
        periodStart: new Date().toISOString(),
        periodEnd: new Date().toISOString(),
        grossAmount: 10000,
        netAmount: 9000,
        status: "sent",
        breakdowns: [],
        commissions: [],
        payoutBatches: [],
        documents: [],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/documents/") && !url.endsWith("/documents")) {
    return new Response(
      JSON.stringify({
        id: "doc-1",
        type: "Акт",
        period: "2024-01",
        amount: 5000,
        status: "sent",
        files: [],
        signatures: [],
        edoEvents: [],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/settings")) {
    return new Response(
      JSON.stringify({
        profile: { id: "partner-1", name: "Партнёр" },
        integrations: [],
        users: [],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/profile")) {
    return new Response(JSON.stringify({ id: "partner-1", name: "Партнёр" }), { status: 200 });
  }
  if (url.includes("/partner/catalog/") && !url.endsWith("/catalog")) {
    return new Response(
      JSON.stringify({
        id: "catalog-1",
        kind: "SERVICE",
        title: "Мойка",
        description: "Полный комплекс",
        category: "Автомойка",
        baseUom: "услуга",
        status: "ACTIVE",
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        activeOffersCount: 1,
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/catalog")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "catalog-1",
            kind: "SERVICE",
            title: "Мойка",
            description: "Полный комплекс",
            category: "Автомойка",
            baseUom: "услуга",
            status: "ACTIVE",
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            activeOffersCount: 1,
          },
        ],
        page: 1,
        pageSize: 10,
        total: 1,
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/offers")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "offer-1",
            catalogItemId: "catalog-1",
            locationScope: "all",
            price: 500,
            currency: "RUB",
            vatRate: 20,
            availability: "always",
            active: true,
            validFrom: new Date().toISOString(),
            validTo: new Date().toISOString(),
          },
        ],
        page: 1,
        pageSize: 10,
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

describe("Partner pages", () => {
  it("renders stations page", async () => {
    render(
      <MemoryRouter initialEntries={["/stations"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/АЗС партнёра/)).toBeInTheDocument();
  });

  it("renders station details page", async () => {
    render(
      <MemoryRouter initialEntries={["/stations/station-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/АЗС Север/)).toBeInTheDocument();
  });

  it("renders transactions page", async () => {
    render(
      <MemoryRouter initialEntries={["/transactions"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Операции партнёра/)).toBeInTheDocument();
  });

  it("renders prices page", async () => {
    render(
      <MemoryRouter initialEntries={["/prices"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Цены/)).toBeInTheDocument();
  });

  it("renders price version details page", async () => {
    render(
      <MemoryRouter initialEntries={["/prices/version-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Версия/)).toBeInTheDocument();
  });

  it("renders transaction details page", async () => {
    render(
      <MemoryRouter initialEntries={["/transactions/tx-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Операция/)).toBeInTheDocument();
  });

  it("renders documents page", async () => {
    render(
      <MemoryRouter initialEntries={["/documents"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: /Документы/ })).toBeInTheDocument();
  });

  it("renders document detail page", async () => {
    render(
      <MemoryRouter initialEntries={["/documents/doc-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Акт/)).toBeInTheDocument();
  });

  it("renders services catalog page", async () => {
    render(
      <MemoryRouter initialEntries={["/services"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Каталог услуг и товаров/)).toBeInTheDocument();
  });

  it("renders service details page", async () => {
    render(
      <MemoryRouter initialEntries={["/services/catalog-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Мойка/)).toBeInTheDocument();
  });

  it("renders settings page", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: /Настройки/ })).toBeInTheDocument();
  });
});

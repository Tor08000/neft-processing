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

    expect(await screen.findByText(/Документы/)).toBeInTheDocument();
  });

  it("renders document detail page", async () => {
    render(
      <MemoryRouter initialEntries={["/documents/doc-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Акт/)).toBeInTheDocument();
  });

  it("renders services page", async () => {
    render(
      <MemoryRouter initialEntries={["/services"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Каталог сервисов/)).toBeInTheDocument();
  });

  it("renders settings page", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Настройки/)).toBeInTheDocument();
  });
});

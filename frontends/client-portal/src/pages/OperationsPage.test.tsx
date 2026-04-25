import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { AuthProvider } from "../auth/AuthContext";
import type { AuthSession } from "../api/types";
import { OperationDetailsPage } from "./OperationDetailsPage";
import { OperationsPage } from "./OperationsPage";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

function StationMapRouteProbe() {
  const location = useLocation();
  return <div data-testid="station-map-route">{location.search}</div>;
}

describe("Client operations", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.stubEnv("VITE_DEMO_MODE", "true");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("renders list with filters and pagination", async () => {
    const cardsResponse = new Response(
      JSON.stringify({ items: [{ id: "card-1", pan_masked: "1111", status: "ACTIVE", limits: [] }] }),
      { status: 200 },
    );
    const operationsResponse = new Response(
      JSON.stringify({
        items: [
          {
            id: "op-1",
            created_at: "2024-01-01T10:00:00Z",
            amount: 1000,
            currency: "RUB",
            status: "APPROVED",
            card_id: "card-1",
            merchant_id: "azs-7",
            product_type: "DIESEL",
            quantity: 20,
          },
        ],
        total: 1,
        limit: 10,
        offset: 0,
      }),
      { status: 200 },
    );
    const filteredResponse = new Response(
      JSON.stringify({
        items: [],
        total: 0,
        limit: 10,
        offset: 0,
      }),
      { status: 200 },
    );

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(cardsResponse)
      .mockResolvedValueOnce(operationsResponse)
      .mockResolvedValueOnce(filteredResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/operations"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: /Операции/i })).toBeInTheDocument();
    expect(await screen.findByText(/azs-7/)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/Статус/i), "DECLINED");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const lastCall = fetchMock.mock.calls[2]?.[0] as string;
    expect(lastCall).toContain("status=DECLINED");
  });

  it("opens operation details", async () => {
    const detailResponse = new Response(
      JSON.stringify({
        id: "op-2",
        created_at: "2024-01-02T12:00:00Z",
        amount: 1500,
        currency: "RUB",
        status: "DECLINED",
        card_id: "card-9",
        merchant_id: "azs-9",
        product_type: "AI95",
        quantity: 30,
        reason: "Превышен дневной лимит договора",
      }),
      { status: 200 },
    );

    const fetchMock = vi.fn().mockResolvedValue(detailResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/operations/op-2"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Превышен дневной лимит договора/)).toBeInTheDocument();
    expect(screen.getByText(/op-2/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Скачать чек (если доступен)" })).not.toBeInTheDocument();
  });

  it("keeps backend failures visible instead of switching demo accounts to synthetic operations", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "gateway failed" }), { status: 500 }));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/operations"]}>
        <AuthProvider initialSession={session}>
          <Routes>
            <Route path="/operations" element={<OperationsPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Расходы недоступны")).toBeInTheDocument();
    expect(screen.queryByText("Фильтры работают в демо-режиме, данные обновляются локально.")).not.toBeInTheDocument();
    expect(screen.queryByText("op-1")).not.toBeInTheDocument();
  });

  it("shows station actions and opens map with station id", async () => {
    const detailResponse = new Response(
      JSON.stringify({
        id: "op-st-1",
        created_at: "2024-01-02T12:00:00Z",
        amount: 1500,
        currency: "RUB",
        status: "APPROVED",
        card_id: "card-9",
        station: {
          id: "station-123",
          name: "АЗС 123",
          address: "RU, Moscow",
          nav_url: "https://maps.example/nav",
        },
      }),
      { status: 200 },
    );

    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    const fetchMock = vi.fn().mockResolvedValue(detailResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/operations/op-st-1"]}>
        <AuthProvider initialSession={session}>
          <Routes>
            <Route path="/operations/:id" element={<OperationDetailsPage />} />
            <Route path="/stations-map" element={<StationMapRouteProbe />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    const navButton = await screen.findByRole("button", { name: "Проложить маршрут" });
    expect(navButton).toBeEnabled();
    await userEvent.click(navButton);
    expect(openSpy).toHaveBeenCalledWith("https://maps.example/nav", "_blank", "noopener,noreferrer");

    await userEvent.click(screen.getByRole("button", { name: "Показать на карте" }));
    expect(await screen.findByTestId("station-map-route")).toHaveTextContent("?station_id=station-123");
  });

  it("shows an honest notice instead of a disabled route action when station nav_url is missing", async () => {
    const detailResponse = new Response(
      JSON.stringify({
        id: "op-st-2",
        created_at: "2024-01-02T12:00:00Z",
        amount: 1500,
        currency: "RUB",
        status: "APPROVED",
        card_id: "card-9",
        station: { id: "station-124", name: "АЗС 124", address: "RU, Moscow", nav_url: null },
      }),
      { status: 200 },
    );

    const fetchMock = vi.fn().mockResolvedValue(detailResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/operations/op-st-2"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Координаты станции недоступны.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Проложить маршрут" })).not.toBeInTheDocument();
  });

});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { TripDetailsPage } from "./TripDetailsPage";
import type { AuthSession } from "../../api/types";
import {
  fetchTripById,
  fetchTripDeviations,
  fetchTripEta,
  fetchTripPosition,
  fetchTripRoute,
  fetchTripSlaImpact,
  fetchTripTracking,
  fetchTripFuel,
} from "../../api/logistics";

vi.mock("../../api/logistics", () => ({
  fetchTripById: vi.fn(),
  fetchTripRoute: vi.fn(),
  fetchTripTracking: vi.fn(),
  fetchTripEta: vi.fn(),
  fetchTripPosition: vi.fn(),
  fetchTripDeviations: vi.fn(),
  fetchTripSlaImpact: vi.fn(),
  fetchTripFuel: vi.fn(),
}));

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const inProgressTrip = {
  id: "trip-1",
  status: "IN_PROGRESS" as const,
  vehicle: { id: "veh-1", plate: "A123BC77" },
  driver: { id: "drv-1", name: "Иванов Иван" },
  origin: { label: "Москва" },
  destination: { label: "Тула" },
  start_planned_at: "2026-02-08T10:00:00Z",
  end_planned_at: "2026-02-08T14:00:00Z",
  start_actual_at: "2026-02-08T10:10:00Z",
  end_actual_at: null,
  updated_at: "2026-02-08T10:10:00Z",
  route: {
    trip_id: "trip-1",
    distance_km: 180.5,
    eta_minutes: 150,
    stops: [{ seq: 1, type: "START" as const, label: "Москва", planned_at: "2026-02-08T10:00:00Z", actual_at: null }],
  },
  meta: {},
};

function renderPage() {
  render(
    <AuthProvider initialSession={session}>
      <MemoryRouter initialEntries={["/logistics/trips/trip-1"]}>
        <Routes>
          <Route path="/logistics/trips/:tripId" element={<TripDetailsPage />} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

type MockCall = [unknown, ...unknown[]];

describe("TripDetailsPage", () => {
  beforeEach(() => {
    vi.mocked(fetchTripById).mockResolvedValue(inProgressTrip);
    vi.mocked(fetchTripRoute).mockResolvedValue({ trip_id: "trip-1", stops: [] });
    vi.mocked(fetchTripTracking).mockResolvedValue({
      trip_id: "trip-1",
      items: [{ ts: "2026-02-08T10:15:00Z", lat: 55.7558, lon: 37.6173, speed_kmh: 52.3, accuracy_m: 12 }],
      last: { ts: "2026-02-08T10:15:00Z", lat: 55.7558, lon: 37.6173, speed_kmh: 52.3, accuracy_m: 12 },
    });
    vi.mocked(fetchTripEta).mockResolvedValue({
      trip_id: "trip-1",
      eta_at: "2026-02-08T12:40:00Z",
      eta_minutes: 75,
      updated_at: "2026-02-08T11:25:00Z",
      method: "simple",
      confidence: 0.7,
    });
    vi.mocked(fetchTripPosition).mockResolvedValue({ ts: "2026-02-08T10:15:00Z", lat: 55.7558, lon: 37.6173 });
    vi.mocked(fetchTripDeviations).mockResolvedValue({
      trip_id: "trip-1",
      items: [
        {
          id: "dev-1",
          ts: "2026-02-08T11:05:00Z",
          type: "LATE_START",
          severity: "WARN",
          title: "Late departure",
          details: "Driver started later than planned",
          evidence: { delta_minutes: 18 },
          sla_impact: { impact_level: "LOW", first_response_due_at: "2026-02-08T11:30:00Z", resolve_due_at: "2026-02-08T13:00:00Z" },
        },
      ],
    });
    vi.mocked(fetchTripSlaImpact).mockResolvedValue({
      trip_id: "trip-1",
      impact_level: "LOW",
      first_response_due_at: "2026-02-08T11:30:00Z",
      resolve_due_at: "2026-02-08T13:00:00Z",
      updated_at: "2026-02-08T11:10:00Z",
      signals: [{ type: "LATE_START", severity: "WARN", delta_minutes: 18 }],
    });
    vi.mocked(fetchTripFuel).mockResolvedValue({
      trip_id: "trip-1",
      items: [{ id: "ftx-1", ts: "2026-02-08T11:00:00Z", vehicle_id: "veh-1", driver_id: "drv-1", liters: 40, amount: 3200, station_name: "AZS-1" }],
      totals: { liters: 40, amount: 3200 },
      alerts: [],
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("renders tracking tab", async () => {
    renderPage();
    expect(await screen.findByText(/Статусная лента|Status timeline/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Трекинг|Tracking/ }));
    expect(await screen.findByText(/Последняя позиция|Last known position/)).toBeInTheDocument();
    expect(screen.getByText(/Обновления ETA|ETA updates/)).toBeInTheDocument();
  });

  it("enables polling only for IN_PROGRESS on active tracking tab", async () => {
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");

    renderPage();
    await screen.findByText(/Статусная лента|Status timeline/);
    const intervalCalls = setIntervalSpy.mock.calls as MockCall[];
    const appIntervalsBefore = intervalCalls.filter((call) => call[1] === 10000 || call[1] === 30000);
    expect(appIntervalsBefore).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /Трекинг|Tracking/ }));
    await screen.findByText(/Последняя позиция|Last known position/);

    const appIntervals = intervalCalls.filter((call) => call[1] === 10000 || call[1] === 30000);
    expect(appIntervals).toHaveLength(2);
    expect(appIntervals[0]?.[1]).toBe(10000);
    expect(appIntervals[1]?.[1]).toBe(30000);

    fireEvent.click(screen.getByRole("button", { name: /Маршрут|Route/ }));
    await waitFor(() => expect(clearIntervalSpy).toHaveBeenCalled());
  });

  it("disables polling for COMPLETED trip", async () => {
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    vi.mocked(fetchTripById).mockResolvedValue({ ...inProgressTrip, status: "COMPLETED" });

    renderPage();
    await screen.findByText(/Статусная лента|Status timeline/);
    fireEvent.click(screen.getByRole("button", { name: /Трекинг|Tracking/ }));
    await screen.findByText(/Последняя позиция|Last known position/);

    const intervalCalls = setIntervalSpy.mock.calls as MockCall[];
    const appIntervals = intervalCalls.filter((call) => call[1] === 10000 || call[1] === 30000);
    expect(appIntervals).toHaveLength(0);
  });

  it("shows error state and retry for tracking", async () => {
    vi.mocked(fetchTripTracking)
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce({ trip_id: "trip-1", items: [], last: null });

    renderPage();
    await screen.findByText(/Статусная лента|Status timeline/);
    fireEvent.click(screen.getByRole("button", { name: /Трекинг|Tracking/ }));
    expect((await screen.findAllByText("boom")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /Повторить|Retry/ }));
    await waitFor(() => expect(fetchTripTracking).toHaveBeenCalledTimes(2));
  });

  it("changes window selector and refetches with since parameter", async () => {
    renderPage();
    await screen.findByText(/Статусная лента|Status timeline/);
    fireEvent.click(screen.getByRole("button", { name: /Трекинг|Tracking/ }));
    await screen.findByText(/Последняя позиция|Last known position/);

    const before = vi.mocked(fetchTripTracking).mock.calls.length;
    fireEvent.change(screen.getByRole("combobox", { name: /Окно трекинга|Tracking window/ }), { target: { value: "24h" } });

    await waitFor(() => expect(fetchTripTracking).toHaveBeenCalledTimes(before + 1));
    const lastCall = vi.mocked(fetchTripTracking).mock.calls.at(-1);
    expect(lastCall?.[2]).toMatchObject({ limit: 200 });
    expect(typeof lastCall?.[2]?.since).toBe("string");
  });

  it("renders deviations tab and list", async () => {
    renderPage();
    await screen.findByText(/Статусная лента|Status timeline/);
    fireEvent.click(screen.getByRole("button", { name: /Отклонения|Deviations/ }));
    expect(await screen.findByText(/Влияние на SLA|SLA impact/)).toBeInTheDocument();
    expect(screen.getByText("Late departure")).toBeInTheDocument();
  });

  it("changes deviation type filter and refetches", async () => {
    renderPage();
    await screen.findByText(/Статусная лента|Status timeline/);
    fireEvent.click(screen.getByRole("button", { name: /Отклонения|Deviations/ }));
    await screen.findByText("Late departure");

    const before = vi.mocked(fetchTripDeviations).mock.calls.length;
    fireEvent.change(screen.getByRole("combobox", { name: /Тип отклонения|Deviation type/ }), { target: { value: "ROUTE_DEVIATION" } });
    await waitFor(() => expect(vi.mocked(fetchTripDeviations).mock.calls.length).toBeGreaterThan(before));
    const lastCall = vi.mocked(fetchTripDeviations).mock.calls.at(-1);
    expect(lastCall?.[2]).toMatchObject({ type: "ROUTE_DEVIATION" });
  });

  it("enables deviations polling only for IN_PROGRESS on deviations tab", async () => {
    const setIntervalSpy = vi.spyOn(window, "setInterval");
    renderPage();
    await screen.findByText(/Статусная лента|Status timeline/);

    const intervalCalls = setIntervalSpy.mock.calls as MockCall[];
    const before = intervalCalls.filter((call) => call[1] === 30000).length;
    fireEvent.click(screen.getByRole("button", { name: /Отклонения|Deviations/ }));
    await screen.findByText(/Влияние на SLA|SLA impact/);

    const after = intervalCalls.filter((call) => call[1] === 30000).length;
    expect(after).toBeGreaterThan(before);
  });

  it("shows deviations error and retry", async () => {
    vi.mocked(fetchTripDeviations)
      .mockRejectedValueOnce(new Error("deviations boom"))
      .mockRejectedValueOnce(new Error("deviations boom"))
      .mockResolvedValueOnce({ trip_id: "trip-1", items: [] });

    renderPage();
    await screen.findByText(/Статусная лента|Status timeline/);
    fireEvent.click(screen.getByRole("button", { name: /Отклонения|Deviations/ }));
    expect(await screen.findByText(/Ошибка загрузки отклонений|Unable to load deviations/)).toBeInTheDocument();

    const beforeRetry = vi.mocked(fetchTripDeviations).mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Повторить|Retry/ }));
    await waitFor(() => expect(vi.mocked(fetchTripDeviations).mock.calls.length).toBeGreaterThan(beforeRetry));
  });

  it("renders fuel tab", async () => {
    renderPage();
    await screen.findByText(/Статусная лента|Status timeline/);
    fireEvent.click(screen.getByRole("button", { name: /Fuel/ }));
    expect(await screen.findByText("AZS-1")).toBeInTheDocument();
    expect(screen.getAllByText("40").length).toBeGreaterThan(0);
  });

});

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { TripsPage } from "./TripsPage";
import type { AuthSession } from "../../api/types";
import { createTrip, fetchTrips } from "../../api/logistics";

vi.mock("../../api/logistics", () => ({
  createTrip: vi.fn(),
  fetchTrips: vi.fn(),
}));

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("TripsPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders trips list", async () => {
    vi.mocked(fetchTrips).mockResolvedValue({
      items: [
        {
          id: "trip-1",
          status: "CREATED",
          vehicle: { id: "veh-1", plate: "A123BC77" },
          driver: { id: "drv-1", name: "Иванов Иван" },
          origin: { label: "Москва" },
          destination: { label: "Тула" },
          start_planned_at: "2026-02-08T10:00:00Z",
          end_planned_at: "2026-02-08T14:00:00Z",
          start_actual_at: null,
          end_actual_at: null,
          updated_at: "2026-02-08T10:00:00Z",
        },
      ],
      total: 1,
      limit: 10,
      offset: 0,
    });

    render(
      <MemoryRouter initialEntries={["/logistics/trips"]}>
        <AuthProvider initialSession={session}>
          <TripsPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("A123BC77")).toBeInTheDocument();
    expect(screen.getByText(/Москва → Тула/)).toBeInTheDocument();
  });

  it("shows empty state", async () => {
    vi.mocked(fetchTrips).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });

    render(
      <MemoryRouter initialEntries={["/logistics/trips"]}>
        <AuthProvider initialSession={session}>
          <TripsPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Рейсов нет|No trips/)).toBeInTheDocument();
  });

  it("retries after error", async () => {
    vi.mocked(fetchTrips)
      .mockRejectedValueOnce(new Error("Ошибка"))
      .mockResolvedValueOnce({
        items: [
          {
            id: "trip-2",
            status: "IN_PROGRESS",
            vehicle: { id: "veh-2", plate: "B456CD77" },
            driver: { id: "drv-2", name: "Петров Пётр" },
            origin: { label: "Тверь" },
            destination: { label: "Рязань" },
            start_planned_at: "2026-02-09T10:00:00Z",
            end_planned_at: "2026-02-09T14:00:00Z",
            start_actual_at: "2026-02-09T10:10:00Z",
            end_actual_at: null,
            updated_at: "2026-02-09T10:00:00Z",
          },
        ],
        total: 1,
        limit: 10,
        offset: 0,
      });

    render(
      <MemoryRouter initialEntries={["/logistics/trips"]}>
        <AuthProvider initialSession={session}>
          <TripsPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Ошибка загрузки рейсов|Unable to load trips/)).toBeInTheDocument();

    const retryButton = screen.getByRole("button", { name: /Повторить|Retry/ });
    await userEvent.click(retryButton);

    expect(await screen.findByText("B456CD77")).toBeInTheDocument();
  });

  it("refetches when status filter changes", async () => {
    vi.mocked(fetchTrips).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });

    render(
      <MemoryRouter initialEntries={["/logistics/trips"]}>
        <AuthProvider initialSession={session}>
          <TripsPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    await screen.findByText(/Рейсов нет|No trips/);

    const statusSelect = screen.getByRole("combobox", { name: /Статус|Status/ });
    await userEvent.selectOptions(statusSelect, "IN_PROGRESS");

    expect(fetchTrips).toHaveBeenLastCalledWith(
      session.token,
      expect.objectContaining({ status: "IN_PROGRESS" }),
    );
  });

  it("creates a trip and reloads the list", async () => {
    vi.mocked(fetchTrips).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });
    vi.mocked(createTrip).mockResolvedValue({
      id: "trip-created",
      status: "CREATED",
      title: "Moscow to Tula",
      origin: { label: "Moscow", lat: 55.75, lon: 37.61 },
      destination: { label: "Tula", lat: 54.2, lon: 37.62 },
      updated_at: "2026-02-08T10:00:00Z",
    });

    render(
      <MemoryRouter initialEntries={["/logistics/trips"]}>
        <AuthProvider initialSession={session}>
          <TripsPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    await screen.findByText(/Р РµР№СЃРѕРІ РЅРµС‚|Рейсов нет|No trips/);
    await userEvent.click(screen.getByRole("button", { name: /РЎРѕР·РґР°С‚СЊ СЂРµР№СЃ|Создать рейс|Create trip/ }));
    const dialog = within(screen.getByRole("dialog"));
    await userEvent.type(dialog.getByLabelText(/РќР°Р·РІР°РЅРёРµ|Название|Title/), "Moscow to Tula");
    await userEvent.type(dialog.getByLabelText(/РћС‚РєСѓРґР°|Откуда|Origin/), "Moscow");
    await userEvent.type(dialog.getByLabelText(/РљСѓРґР°|Куда|Destination/), "Tula");
    await userEvent.type(dialog.getByLabelText(/РЁРёСЂРѕС‚Р° РѕС‚РїСЂР°РІР»РµРЅРёСЏ|Широта отправления|Origin latitude/), "55.75");
    await userEvent.type(dialog.getByLabelText(/Р”РѕР»РіРѕС‚Р° РѕС‚РїСЂР°РІР»РµРЅРёСЏ|Долгота отправления|Origin longitude/), "37.61");
    await userEvent.type(dialog.getByLabelText(/РЁРёСЂРѕС‚Р° РЅР°Р·РЅР°С‡РµРЅРёСЏ|Широта назначения|Destination latitude/), "54.2");
    await userEvent.type(dialog.getByLabelText(/Р”РѕР»РіРѕС‚Р° РЅР°Р·РЅР°С‡РµРЅРёСЏ|Долгота назначения|Destination longitude/), "37.62");
    await userEvent.click(dialog.getByRole("button", { name: /РЎРѕР·РґР°С‚СЊ СЂРµР№СЃ|Создать рейс|Create trip/ }));

    expect(createTrip).toHaveBeenCalledWith(
      session.token,
      expect.objectContaining({
        title: "Moscow to Tula",
        origin: { label: "Moscow", lat: 55.75, lon: 37.61 },
        destination: { label: "Tula", lat: 54.2, lon: 37.62 },
      }),
    );
    expect(fetchTrips).toHaveBeenCalledTimes(2);
  });
});

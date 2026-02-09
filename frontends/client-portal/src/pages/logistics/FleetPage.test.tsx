import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { FleetPage } from "./FleetPage";
import type { AuthSession } from "../../api/types";
import { fetchDrivers, fetchVehicles } from "../../api/logistics";

vi.mock("../../api/logistics", () => ({
  fetchVehicles: vi.fn(),
  fetchDrivers: vi.fn(),
}));

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("FleetPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders vehicles list", async () => {
    vi.mocked(fetchVehicles).mockResolvedValue({
      items: [
        {
          id: "veh-1",
          plate: "A123BC77",
          vin: "VIN-1",
          make: "Ford",
          model: "Transit",
          fuel_type: "DT",
          status: "ACTIVE",
          meta: {},
        },
      ],
      total: 1,
      limit: 10,
      offset: 0,
    });
    vi.mocked(fetchDrivers).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });

    render(
      <MemoryRouter initialEntries={["/logistics/fleet"]}>
        <AuthProvider initialSession={session}>
          <FleetPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("A123BC77")).toBeInTheDocument();
  });

  it("shows empty state when no vehicles", async () => {
    vi.mocked(fetchVehicles).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });

    render(
      <MemoryRouter initialEntries={["/logistics/fleet"]}>
        <AuthProvider initialSession={session}>
          <FleetPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Нет ТС|No vehicles/)).toBeInTheDocument();
  });

  it("retries after error", async () => {
    vi.mocked(fetchVehicles)
      .mockRejectedValueOnce(new Error("Ошибка"))
      .mockResolvedValueOnce({
        items: [{ id: "veh-2", plate: "B456CD77", status: "ACTIVE", meta: {} }],
        total: 1,
        limit: 10,
        offset: 0,
      });

    render(
      <MemoryRouter initialEntries={["/logistics/fleet"]}>
        <AuthProvider initialSession={session}>
          <FleetPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Не удалось загрузить данные логистики|Unable to load logistics data/)).toBeInTheDocument();

    const retryButton = screen.getByRole("button", { name: /Повторить|Retry/ });
    await userEvent.click(retryButton);

    expect(await screen.findByText("B456CD77")).toBeInTheDocument();
  });

  it("loads drivers on tab switch", async () => {
    vi.mocked(fetchVehicles).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });
    vi.mocked(fetchDrivers).mockResolvedValue({
      items: [{ id: "drv-1", name: "Иванов Иван", phone: "+79991234567", status: "ACTIVE", meta: {} }],
      total: 1,
      limit: 10,
      offset: 0,
    });

    render(
      <MemoryRouter initialEntries={["/logistics/fleet"]}>
        <AuthProvider initialSession={session}>
          <FleetPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    const driversTab = await screen.findByRole("button", { name: /Водители|Drivers/ });
    await userEvent.click(driversTab);

    expect(await screen.findByText("Иванов Иван")).toBeInTheDocument();
    expect(fetchDrivers).toHaveBeenCalled();
  });
});

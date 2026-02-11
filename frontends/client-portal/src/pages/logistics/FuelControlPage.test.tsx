import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { FuelControlPage } from "./FuelControlPage";

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ user: { token: "token" } }),
}));

const api = vi.hoisted(() => ({
  fetchUnlinkedFuel: vi.fn(async () => [{ fuel_tx_id: "1", station: "S", best_score: 50 }]),
  fetchFuelAlerts: vi.fn(async () => [{ id: "a1", type: "OUT_OF_ROUTE", severity: "WARN", title: "Alert" }]),
  fetchFuelReport: vi.fn(async () => [{ group: "trip-1", liters: 10, amount: 100 }]),
  runFuelLinker: vi.fn(async () => ({ processed: 1, linked: 1, unlinked: 0, alerts_created: 0 })),
}));

vi.mock("../../api/logistics", () => api);

describe("FuelControlPage", () => {
  it("renders tabs and runs linker", async () => {
    render(
      <MemoryRouter>
        <FuelControlPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Fuel Control")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Запустить привязку"));
    await waitFor(() => expect(api.runFuelLinker).toHaveBeenCalled());

    fireEvent.click(screen.getByText("Alerts"));
    expect(await screen.findByText("Alert")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Reports"));
    expect(await screen.findByText("trip-1")).toBeInTheDocument();
  });
});

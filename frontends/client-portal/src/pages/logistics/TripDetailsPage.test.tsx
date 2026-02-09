import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { TripDetailsPage } from "./TripDetailsPage";
import type { AuthSession } from "../../api/types";
import { fetchTripById, fetchTripRoute } from "../../api/logistics";

vi.mock("../../api/logistics", () => ({
  fetchTripById: vi.fn(),
  fetchTripRoute: vi.fn(),
}));

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("TripDetailsPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders stops and timeline", async () => {
    vi.mocked(fetchTripById).mockResolvedValue({
      id: "trip-1",
      status: "IN_PROGRESS",
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
        stops: [
          { seq: 1, type: "START", label: "Москва", planned_at: "2026-02-08T10:00:00Z", actual_at: null },
          { seq: 2, type: "STOP", label: "Заправка", planned_at: "2026-02-08T11:00:00Z", actual_at: null },
          { seq: 3, type: "END", label: "Тула", planned_at: "2026-02-08T14:00:00Z", actual_at: null },
        ],
      },
      meta: {},
    });
    vi.mocked(fetchTripRoute).mockResolvedValue({
      trip_id: "trip-1",
      stops: [],
    });

    render(
      <AuthProvider initialSession={session}>
        <MemoryRouter initialEntries={["/logistics/trips/trip-1"]}>
          <Routes>
            <Route path="/logistics/trips/:tripId" element={<TripDetailsPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(await screen.findByText("Москва")).toBeInTheDocument();
    expect(screen.getByText(/Статусная лента|Status timeline/)).toBeInTheDocument();
    expect(screen.getByText(/В пути|In progress/)).toBeInTheDocument();
  });
});

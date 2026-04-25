import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import LogisticsInspectionPage from "./LogisticsInspectionPage";
import * as logisticsApi from "../../api/logistics";

const useAuthMock = vi.fn();
const useAdminMock = vi.fn();

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../../admin/AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

vi.mock("../../api/logistics", () => ({
  fetchLogisticsInspection: vi.fn(),
  recomputeLogisticsEta: vi.fn(),
}));

const renderPage = (initialEntry = "/logistics/inspection?order_id=order-1") => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <LogisticsInspectionPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("LogisticsInspectionPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "token" });
    useAdminMock.mockReturnValue({
      profile: {
        permissions: { ops: { read: true, operate: true } },
        read_only: false,
      },
    });
    vi.mocked(logisticsApi.fetchLogisticsInspection).mockResolvedValue({
      order: {
        id: "order-1",
        tenant_id: 1,
        client_id: "client-1",
        order_type: "DELIVERY",
        status: "IN_PROGRESS",
        origin_text: "A",
        destination_text: "B",
        created_at: "2026-04-13T10:00:00Z",
        updated_at: "2026-04-13T10:05:00Z",
      },
      active_route: {
        id: "route-1",
        order_id: "order-1",
        version: 2,
        status: "ACTIVE",
        distance_km: 10,
        planned_duration_minutes: 45,
        created_at: "2026-04-13T10:00:00Z",
      },
      routes: [
        {
          id: "route-1",
          order_id: "order-1",
          version: 2,
          status: "ACTIVE",
          distance_km: 10,
          planned_duration_minutes: 45,
          created_at: "2026-04-13T10:00:00Z",
        },
      ],
      active_route_stops: [
        {
          id: "stop-1",
          route_id: "route-1",
          sequence: 0,
          stop_type: "PICKUP",
          name: "Warehouse",
          status: "PLANNED",
        },
      ],
      latest_eta_snapshot: {
        id: "eta-1",
        order_id: "order-1",
        computed_at: "2026-04-13T10:10:00Z",
        eta_end_at: "2026-04-13T11:10:00Z",
        eta_confidence: 82,
        method: "ROUTE_MODEL",
        created_at: "2026-04-13T10:10:00Z",
      },
      latest_route_snapshot: {
        id: "snap-1",
        order_id: "order-1",
        route_id: "route-1",
        provider: "local",
        geometry: [],
        distance_km: 10,
        eta_minutes: 45,
        created_at: "2026-04-13T10:10:00Z",
      },
      navigator_explains: [
        {
          id: "exp-1",
          route_snapshot_id: "snap-1",
          type: "ETA",
          payload: { reason: "traffic" },
          created_at: "2026-04-13T10:10:00Z",
        },
      ],
      tracking_events_count: 4,
      last_tracking_event: {
        id: "track-1",
        order_id: "order-1",
        event_type: "GPS",
        ts: "2026-04-13T10:12:00Z",
      },
    });
    vi.mocked(logisticsApi.recomputeLogisticsEta).mockResolvedValue({
      id: "eta-2",
      order_id: "order-1",
      computed_at: "2026-04-13T10:20:00Z",
      eta_end_at: "2026-04-13T11:20:00Z",
      eta_confidence: 85,
      method: "ROUTE_MODEL",
      created_at: "2026-04-13T10:20:00Z",
    });
  });

  it("renders grounded logistics inspection and allows eta recompute for operator roles", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("order-1")).toBeInTheDocument();
    expect(screen.getByText("Warehouse")).toBeInTheDocument();
    expect(screen.getByText(/Stored navigator explain payloads/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Recompute ETA" }));

    expect(logisticsApi.recomputeLogisticsEta).toHaveBeenCalledWith("token", "order-1");
  });

  it("keeps recompute disabled in read-only mode", async () => {
    useAdminMock.mockReturnValue({
      profile: {
        permissions: { ops: { read: true, operate: false } },
        read_only: true,
      },
    });

    renderPage();

    expect(await screen.findByText("order-1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Recompute ETA" })).toBeDisabled();
    expect(screen.getByText(/Read-only mode: ETA recompute disabled/)).toBeInTheDocument();
  });

  it("renders an honest first-use state before an order is selected", async () => {
    renderPage("/logistics/inspection");

    expect(await screen.findByRole("heading", { name: "Inspection is not open yet" })).toBeInTheDocument();
    expect(screen.queryByText("order-1")).not.toBeInTheDocument();
  });
});

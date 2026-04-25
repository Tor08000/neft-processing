import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/http";
import { DashboardPage } from "./DashboardPage";

const useAuthMock = vi.fn();
const useClientMock = vi.fn();
const fetchClientDashboardMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => useClientMock(),
}));

vi.mock("../api/portal", () => ({
  fetchClientDashboard: (...args: unknown[]) => fetchClientDashboardMock(...args),
}));

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({
      user: { token: "test.header.payload", email: "client@corp.local" },
      logout: vi.fn(),
    });
    useClientMock.mockReturnValue({
      client: {
        access_state: "ACTIVE",
        user: { email: "client@corp.local" },
      },
      isLoading: false,
      error: null,
      portalState: "READY",
      refresh: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders a route-specific dashboard error state without raw payload in primary UI", async () => {
    fetchClientDashboardMock.mockRejectedValue(
      new ApiError(
        JSON.stringify({
          error: "internal_error",
          message: "Internal Server Error",
          request_id: "req-dashboard-1",
        }),
        500,
        "corr-dashboard-1",
        "req-dashboard-1",
        "internal_error",
      ),
    );

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Дашборд временно недоступен")).toBeInTheDocument();
    expect(screen.getByText("Не удалось загрузить дашборд. Попробуйте позже.")).toBeInTheDocument();
    expect(screen.getByText("Код ошибки: 500")).toBeInTheDocument();
    expect(screen.getByText("Request ID: req-dashboard-1")).toBeInTheDocument();
    expect(screen.getByText("Correlation ID: corr-dashboard-1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
    expect(screen.queryByText(/Internal Server Error/)).not.toBeInTheDocument();
  });

  it("renders a first-use dashboard empty state when the owner route has no widgets yet", async () => {
    fetchClientDashboardMock.mockResolvedValue({
      role: "OWNER",
      timezone: "Europe/Moscow",
      widgets: [],
    });

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Дашборд готов, но ещё не наполнен рабочими сигналами")).toBeInTheDocument();
    expect(screen.getByText("Первые карточки появятся после документов, операций, тикетов или аналитики по вашей компании.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть аналитику" })).toBeInTheDocument();
    await waitFor(() => expect(fetchClientDashboardMock).toHaveBeenCalledTimes(1));
  });
});

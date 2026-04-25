import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FleetCardsPage from "./FleetCardsPage";
import FleetLimitsPage from "./FleetLimitsPage";
import FleetSpendPage from "./FleetSpendPage";

const useAuthMock = vi.fn();
const listFleetCardsMock = vi.fn();
const listFleetLimitsMock = vi.fn();
const listFleetGroupsMock = vi.fn();
const getFleetSpendSummaryMock = vi.fn();
const listFleetTransactionsMock = vi.fn();

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../../api/fleet", () => ({
  listFleetCards: (...args: unknown[]) => listFleetCardsMock(...args),
  listFleetLimits: (...args: unknown[]) => listFleetLimitsMock(...args),
  listFleetGroups: (...args: unknown[]) => listFleetGroupsMock(...args),
  getFleetSpendSummary: (...args: unknown[]) => getFleetSpendSummaryMock(...args),
  listFleetTransactions: (...args: unknown[]) => listFleetTransactionsMock(...args),
}));

describe("Fleet list pages", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "admin-token" });
  });

  it("renders shared toolbar and footer on fleet cards list", async () => {
    listFleetCardsMock.mockResolvedValue({
      items: [
        {
          id: "card-1",
          card_alias: "Main card",
          masked_pan: "**** 1234",
          status: "ACTIVE",
          currency: "RUB",
          issued_at: "2026-04-10T10:00:00Z",
          created_at: "2026-04-09T09:00:00Z",
        },
      ],
    });

    render(
      <MemoryRouter>
        <FleetCardsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Main card")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Alias, masked pan, card id")).toBeInTheDocument();
    expect(screen.getByText("Rows: 1")).toBeInTheDocument();
  });

  it("shows filtered-empty reset on fleet cards list", async () => {
    listFleetCardsMock.mockResolvedValue({
      items: [
        {
          id: "card-1",
          card_alias: "Main card",
          masked_pan: "**** 1234",
          status: "ACTIVE",
          currency: "RUB",
          issued_at: "2026-04-10T10:00:00Z",
          created_at: "2026-04-09T09:00:00Z",
        },
      ],
    });

    render(
      <MemoryRouter>
        <FleetCardsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Main card")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Alias, masked pan, card id"), {
      target: { value: "missing-card" },
    });

    expect(await screen.findByText("Карты не найдены")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));

    expect(await screen.findByText("Main card")).toBeInTheDocument();
  });

  it("renders the shared empty prompt for fleet limits before scope selection", () => {
    render(
      <MemoryRouter>
        <FleetLimitsPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Выберите scope для просмотра лимитов")).toBeInTheDocument();
    expect(screen.getByText("Rows: 0")).toBeInTheDocument();
    expect(listFleetLimitsMock).not.toHaveBeenCalled();
  });

  it("renders shared transactions table shell on fleet spend page", async () => {
    listFleetGroupsMock.mockResolvedValue({
      items: [{ id: "group-1", name: "North" }],
    });
    listFleetCardsMock.mockResolvedValue({
      items: [{ id: "card-1", card_alias: "Main card" }],
    });
    getFleetSpendSummaryMock.mockResolvedValue({
      group_by: "day",
      rows: [{ key: "2026-04-10", amount: "1200.00" }],
    });
    listFleetTransactionsMock.mockResolvedValue({
      items: [
        {
          id: "txn-1",
          occurred_at: "2026-04-10T08:00:00Z",
          amount: "1200.00",
          card_id: "card-1",
          merchant_name: "NEFT Station",
          category: "fuel",
          station_id: "station-1",
        },
      ],
    });

    render(
      <MemoryRouter>
        <FleetSpendPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("NEFT Station")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Обновить" })).toBeInTheDocument();
    expect(screen.getByText("Rows: 1")).toBeInTheDocument();
  });
});

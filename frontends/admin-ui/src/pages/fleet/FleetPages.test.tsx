import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import FleetCardsPage from "./FleetCardsPage";
import FleetGroupsPage from "./FleetGroupsPage";
import FleetEmployeesPage from "./FleetEmployeesPage";
import FleetLimitsPage from "./FleetLimitsPage";
import FleetSpendPage from "./FleetSpendPage";
import * as fleetApi from "../../api/fleet";

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "token" }),
}));

vi.mock("../../api/fleet", () => ({
  listFleetCards: vi.fn(),
  listFleetGroups: vi.fn(),
  listFleetEmployees: vi.fn(),
  listFleetLimits: vi.fn(),
  listFleetTransactions: vi.fn(),
  getFleetSpendSummary: vi.fn(),
}));

const renderPage = (ui: React.ReactElement) => {
  render(<MemoryRouter>{ui}</MemoryRouter>);
};

describe("Fleet pages", () => {
  it("renders empty cards state", async () => {
    (fleetApi.listFleetCards as unknown as Mock).mockResolvedValue({ items: [] });

    renderPage(<FleetCardsPage />);

    expect(await screen.findByText("Fleet · Cards")).toBeInTheDocument();
    expect(await screen.findByText("Карты не найдены")).toBeInTheDocument();
  });

  it("renders empty groups state", async () => {
    (fleetApi.listFleetGroups as unknown as Mock).mockResolvedValue({ items: [] });

    renderPage(<FleetGroupsPage />);

    expect(await screen.findByText("Fleet · Groups")).toBeInTheDocument();
    expect(await screen.findByText("Группы не найдены")).toBeInTheDocument();
  });

  it("renders empty employees state", async () => {
    (fleetApi.listFleetEmployees as unknown as Mock).mockResolvedValue({ items: [] });

    renderPage(<FleetEmployeesPage />);

    expect(await screen.findByText("Fleet · Employees")).toBeInTheDocument();
    expect(await screen.findByText("Сотрудники не найдены")).toBeInTheDocument();
  });

  it("renders limits empty prompt before scope selection", async () => {
    renderPage(<FleetLimitsPage />);

    expect(await screen.findByText("Fleet · Limits")).toBeInTheDocument();
    expect(await screen.findByText("Выберите scope для просмотра лимитов")).toBeInTheDocument();
    await waitFor(() => expect(fleetApi.listFleetLimits).not.toHaveBeenCalled());
  });

  it("renders spend summary and empty transactions", async () => {
    (fleetApi.listFleetGroups as unknown as Mock).mockResolvedValue({ items: [] });
    (fleetApi.listFleetCards as unknown as Mock).mockResolvedValue({ items: [] });
    (fleetApi.getFleetSpendSummary as unknown as Mock).mockResolvedValue({ group_by: "day", rows: [] });
    (fleetApi.listFleetTransactions as unknown as Mock).mockResolvedValue({ items: [] });

    renderPage(<FleetSpendPage />);

    expect(await screen.findByText("Fleet · Spend")).toBeInTheDocument();
    expect(await screen.findByText("Нет данных по расходам")).toBeInTheDocument();
    expect(await screen.findByText("Транзакции не найдены")).toBeInTheDocument();
  });
});

import { describe, expect, it, vi, beforeEach } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import BalancesPage from "./BalancesPage";
import * as accountsApi from "../api/accounts";

const sampleAccounts = {
  items: [
    {
      id: 1,
      client_id: "client-1",
      card_id: "card-1",
      tariff_id: null,
      currency: "RUB",
      type: "CLIENT_MAIN",
      status: "ACTIVE",
      balance: 1000,
    },
  ],
  total: 1,
};

vi.mock("../api/accounts", () => ({
  fetchAccounts: vi.fn(),
}));

describe("BalancesPage", () => {
  beforeEach(() => {
    (accountsApi.fetchAccounts as unknown as Mock).mockResolvedValue(sampleAccounts);
  });

  it("renders accounts table", async () => {
    render(
      <MemoryRouter>
        <BalancesPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("client-1")).toBeInTheDocument());
    expect(screen.getByText("Balances")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument();
  });
});

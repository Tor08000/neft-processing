import { describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import AccountDetailsPage from "./AccountDetailsPage";
import * as accountsApi from "../api/accounts";

const statement = {
  account_id: 1,
  entries: [
    {
      id: 10,
      operation_id: "op-1",
      posted_at: new Date("2024-01-01T00:00:00Z").toISOString(),
      direction: "DEBIT",
      amount: 100,
      currency: "RUB",
      balance_after: 900,
    },
  ],
};

vi.mock("../api/accounts", () => ({
  fetchAccountStatement: vi.fn(),
}));

describe("AccountDetailsPage", () => {
  it("renders statement rows", async () => {
    (accountsApi.fetchAccountStatement as unknown as Mock).mockResolvedValue(statement);

    render(
      <MemoryRouter initialEntries={["/accounts/1"]}>
        <Routes>
          <Route path="/accounts/:accountId" element={<AccountDetailsPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Account #1")).toBeInTheDocument());
    expect(screen.getByText("op-1")).toBeInTheDocument();
    expect(screen.getByText("DEBIT")).toBeInTheDocument();
  });
});

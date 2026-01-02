import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import BillingLinksPage from "./BillingLinksPage";
import * as billingApi from "../../api/billing";

vi.mock("../../api/billing", () => ({
  listReconciliationLinks: vi.fn(),
}));

describe("BillingLinksPage", () => {
  beforeEach(() => {
    (billingApi.listReconciliationLinks as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          id: "link_1",
          entity_type: "payment",
          entity_id: "pay_1",
          provider: "bank_stub",
          currency: "RUB",
          expected_amount: 1000,
          direction: "IN",
          expected_at: "2024-01-05T00:00:00Z",
          status: "MISMATCHED",
          run_id: "run_1",
          match_key: "match-1",
          last_run_id: "run_1",
          discrepancy_id: "disc_1",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
  });

  it("renders links and navigates to run", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/billing/links"]}>
        <Routes>
          <Route path="/billing/links" element={<BillingLinksPage />} />
          <Route path="/reconciliation/runs/:id" element={<div>Run details</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("link_1")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Open discrepancies" }));
    expect(await screen.findByText("Run details")).toBeInTheDocument();
  });

  it("applies status filter", async () => {
    render(
      <MemoryRouter>
        <BillingLinksPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("link_1")).toBeInTheDocument());
    const statusLabel = screen.getAllByText("Status").find((node) => node.classList.contains("label"));
    const statusWrapper = statusLabel?.parentElement;
    const statusSelect = statusWrapper?.querySelector("select");
    if (!statusSelect) throw new Error("Status select not found");
    await userEvent.selectOptions(statusSelect, "MISMATCHED");

    await waitFor(() =>
      expect(billingApi.listReconciliationLinks).toHaveBeenCalledWith(expect.objectContaining({ status: "MISMATCHED" })),
    );
  });
});

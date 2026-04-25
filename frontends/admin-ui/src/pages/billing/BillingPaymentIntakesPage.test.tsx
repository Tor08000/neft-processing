import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import BillingPaymentIntakesPage from "./BillingPaymentIntakesPage";
import * as billingApi from "../../api/billing";

vi.mock("../../api/billing", () => ({
  listPaymentIntakes: vi.fn(),
  approvePaymentIntake: vi.fn(),
  rejectPaymentIntake: vi.fn(),
}));

describe("BillingPaymentIntakesPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.stubGlobal("prompt", vi.fn(() => "duplicate receipt"));
  });

  it("prompts for a rejection reason and forwards it to the owner action", async () => {
    (billingApi.listPaymentIntakes as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          id: "pi-1",
          invoice_id: "inv-1",
          org_id: 77,
          amount: "12500.00",
          currency: "RUB",
          status: "UNDER_REVIEW",
          proof_url: null,
          created_at: "2026-04-10T10:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
    (billingApi.rejectPaymentIntake as ReturnType<typeof vi.fn>).mockResolvedValue({});

    render(
      <MemoryRouter>
        <BillingPaymentIntakesPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("inv-1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));

    expect(window.prompt).toHaveBeenCalledWith("Причина отклонения");
    await waitFor(() =>
      expect(billingApi.rejectPaymentIntake).toHaveBeenCalledWith("pi-1", { review_note: "duplicate receipt" }),
    );
  });
});

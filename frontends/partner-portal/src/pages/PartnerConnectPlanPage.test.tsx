import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { PartnerSubscriptionProvider } from "../auth/PartnerSubscriptionContext";
import { PartnerConnectPlanPage } from "./PartnerConnectPlanPage";

describe("PartnerConnectPlanPage", () => {
  it("renders 5 partner plans and persists selection", () => {
    localStorage.clear();
    render(
      <MemoryRouter>
        <PartnerSubscriptionProvider>
          <PartnerConnectPlanPage />
        </PartnerSubscriptionProvider>
      </MemoryRouter>,
    );

    expect(screen.getAllByRole("heading", { level: 2 }).length).toBe(5);
    fireEvent.click(screen.getAllByRole("button", { name: /choose/i })[0]);
    expect(localStorage.getItem("neft_partner_subscription_draft")).toContain("PARTNER_");
  });
});

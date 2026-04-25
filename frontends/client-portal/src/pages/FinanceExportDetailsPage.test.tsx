import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FinanceExportDetailsPage } from "./FinanceExportDetailsPage";

const { fetchExportDetails, authUser } = vi.hoisted(() => ({
  fetchExportDetails: vi.fn(),
  authUser: {
    token: "test.header.payload",
    email: "client@example.test",
    roles: ["CLIENT_OWNER"],
    subjectType: "CLIENT",
    clientId: "client-1",
    expiresAt: Date.now() + 60_000,
  },
}));

vi.mock("../api/exports", () => ({
  fetchExportDetails,
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: authUser,
  }),
}));

describe("FinanceExportDetailsPage", () => {
  beforeEach(() => {
    fetchExportDetails.mockResolvedValue({
      id: "export-1",
      type: "settlement",
      title: "Сверка за март",
      period_from: "2026-03-01",
      period_to: "2026-03-31",
      status: "DONE",
      erp_status: "QUEUED",
      totals: {},
      erp_timeline: [],
      reconciliation: null,
    });
  });

  it("renders export detail sections and support CTA when summary subreads are missing", async () => {
    render(
      <MemoryRouter initialEntries={["/exports/export-1"]}>
        <Routes>
          <Route path="/exports/:id" element={<FinanceExportDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const supportLink = await screen.findByRole("link", { name: "Написать в поддержку" });

    expect(screen.getByText("Export detail")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Totals" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ERP timeline" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Reconciliation" })).toBeInTheDocument();
    expect(supportLink).toHaveAttribute(
      "href",
      "/client/support/new?topic=billing",
    );
  });
});

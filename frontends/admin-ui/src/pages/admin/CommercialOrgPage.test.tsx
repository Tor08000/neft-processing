import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import CommercialOrgPage from "./CommercialOrgPage";
import * as commercialApi from "../../api/commercial";

const useAuthMock = vi.fn();

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../../api/commercial", () => ({
  getCommercialState: vi.fn(),
  getCommercialEntitlements: vi.fn(),
  changeCommercialPlan: vi.fn(),
  disableCommercialAddon: vi.fn(),
  enableCommercialAddon: vi.fn(),
  recomputeCommercialEntitlements: vi.fn(),
  removeCommercialOverride: vi.fn(),
  upsertCommercialOverride: vi.fn(),
}));

const renderPage = (initialEntry: string) =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/commercial" element={<CommercialOrgPage />} />
        <Route path="/commercial/:orgId" element={<CommercialOrgPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("CommercialOrgPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "token-1", logout: vi.fn() });
  });

  it("shows an honest first-use state before an org is selected", async () => {
    renderPage("/commercial");

    expect(screen.getByText("Commercial control is waiting for an org")).toBeInTheDocument();
    expect(commercialApi.getCommercialState).not.toHaveBeenCalled();
    expect(commercialApi.getCommercialEntitlements).not.toHaveBeenCalled();
  });

  it("shows a retryable load error instead of stale org data", async () => {
    vi.mocked(commercialApi.getCommercialState).mockRejectedValue(new Error("owner route unavailable"));
    vi.mocked(commercialApi.getCommercialEntitlements).mockResolvedValue({ current: null, previous: [] });

    const user = userEvent.setup();
    renderPage("/commercial/42");

    expect(await screen.findByText("Commercial control is unavailable")).toBeInTheDocument();
    expect(screen.getByText("Failed to load commercial state.")).toBeInTheDocument();
    expect(screen.queryByText("Organization")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Reload org" }));

    await waitFor(() => expect(commercialApi.getCommercialState).toHaveBeenCalledTimes(2));
    expect(commercialApi.getCommercialState).toHaveBeenLastCalledWith("token-1", 42);
  });
});

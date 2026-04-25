import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FinanceExportsPage } from "./FinanceExportsPage";

const useAuthMock = vi.fn();
const fetchExportsMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../api/exports", () => ({
  fetchExports: (...args: unknown[]) => fetchExportsMock(...args),
}));

vi.mock("../i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: { count?: number }) =>
      key === "exportsPage.footer.rows" ? `Rows: ${params?.count ?? 0}` : key,
  }),
}));

describe("FinanceExportsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({
      user: {
        token: "test.header.payload",
        email: "accountant@neft.test",
        roles: ["CLIENT_ACCOUNTANT"],
      },
    });
  });

  it("renders shared export table actions and footer", async () => {
    fetchExportsMock.mockResolvedValue({
      items: [
        {
          id: "export-1",
          type: "CHARGES",
          status: "GENERATED",
          reconciliation_status: "matched",
          download_url: "/files/export-1.csv",
          created_at: "2026-04-12T10:00:00Z",
        },
      ],
    });

    render(
      <MemoryRouter>
        <FinanceExportsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("CHARGES")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "actions.download" })).toHaveAttribute("href", "/files/export-1.csv");
    expect(screen.getByRole("link", { name: "common.details" })).toHaveAttribute("href", "/exports/export-1");
    expect(screen.getByText("Rows: 1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "actions.confirmReceived" })).not.toBeInTheDocument();
  });

  it("renders shared error state and retries loading", async () => {
    fetchExportsMock.mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce({ items: [] });

    render(
      <MemoryRouter>
        <FinanceExportsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("errors.actionFailedTitle")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "errors.retry" }));

    await waitFor(() => expect(fetchExportsMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("emptyStates.exports.title")).toBeInTheDocument();
  });
});

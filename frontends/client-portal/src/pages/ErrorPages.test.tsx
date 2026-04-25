import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { I18nProvider } from "../i18n";
import { ServiceUnavailablePage } from "./ServiceUnavailablePage";
import { TechErrorPage } from "./TechErrorPage";

const useClientMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock("../auth/ClientContext", () => ({
  useClient: () => useClientMock(),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

function renderWithProviders(node: ReactNode) {
  return render(
    <MemoryRouter>
      <I18nProvider locale="ru">{node}</I18nProvider>
    </MemoryRouter>,
  );
}

describe("client error pages", () => {
  beforeEach(() => {
    useClientMock.mockReset();
    useAuthMock.mockReset();
  });

  it("retries from the service unavailable page through client refresh", () => {
    const refresh = vi.fn();
    useClientMock.mockReturnValue({ refresh, client: null });
    useAuthMock.mockReturnValue({ user: { id: "u-1" } });

    renderWithProviders(<ServiceUnavailablePage />);

    fireEvent.click(screen.getByRole("button"));

    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("shows technical identifiers and returns guests to login", () => {
    const refresh = vi.fn();
    useClientMock.mockReturnValue({
      refresh,
      client: {
        access_reason: "legacy-fallback",
        flags: {
          error_id: "err-17",
          request_id: "req-42",
        },
      },
    });
    useAuthMock.mockReturnValue({ user: null });

    renderWithProviders(<TechErrorPage />);

    expect(screen.getByText("Error ID: err-17")).toBeInTheDocument();
    expect(screen.getByText("Request ID: req-42")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/login");
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ClientControlsPage } from "./ClientControlsPage";

const useAuthMock = vi.fn();
const useClientMock = vi.fn();
const useClientJourneyMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => useClientMock(),
}));

vi.mock("../auth/ClientJourneyContext", () => ({
  useClientJourney: () => useClientJourneyMock(),
}));

vi.mock("./ClientLimitsPage", () => ({
  ClientLimitsPage: () => <div>limits-content</div>,
}));

vi.mock("./ClientUsersPage", () => ({
  ClientUsersPage: () => <div>users-content</div>,
}));

vi.mock("./ClientServicesPage", () => ({
  ClientServicesPage: () => <div>services-content</div>,
}));

vi.mock("./ClientFeaturesPage", () => ({
  ClientFeaturesPage: () => <div>features-content</div>,
}));

describe("ClientControlsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useClientMock.mockReturnValue({
      client: {
        org: { id: "org-1", org_type: "LEGAL" },
        subscription: { plan_code: "CLIENT_BUSINESS" },
        org_roles: ["CLIENT_OWNER"],
        user_roles: ["CLIENT_OWNER"],
        capabilities: ["CLIENT_BILLING"],
        nav_sections: [],
      },
    });
    useClientJourneyMock.mockReturnValue({
      draft: { customerType: "LEGAL_ENTITY" },
    });
  });

  it("shows the users tab for all client management roles", () => {
    useAuthMock.mockReturnValue({
      user: {
        token: "test.header.payload",
        roles: ["CLIENT_OWNER"],
      },
    });

    const { rerender } = render(<ClientControlsPage />);

    expect(screen.getByRole("button", { name: "Пользователи" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Лимиты" })).toHaveAttribute("aria-pressed", "true");

    useAuthMock.mockReturnValue({
      user: {
        token: "test.header.payload",
        roles: ["CLIENT_MANAGER"],
      },
    });

    rerender(<ClientControlsPage />);

    expect(screen.getByRole("button", { name: "Пользователи" })).toBeInTheDocument();

    useAuthMock.mockReturnValue({
      user: {
        token: "test.header.payload",
        roles: ["CLIENT_USER"],
      },
    });

    rerender(<ClientControlsPage />);

    expect(screen.queryByRole("button", { name: "Пользователи" })).not.toBeInTheDocument();
  });

  it("switches shared control tabs without a card-shell wrapper", () => {
    useAuthMock.mockReturnValue({
      user: {
        token: "test.header.payload",
        roles: ["CLIENT_ADMIN"],
      },
    });

    render(<ClientControlsPage />);

    expect(screen.getByText("limits-content")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Возможности" }));

    expect(screen.getByRole("button", { name: "Возможности" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("features-content")).toBeInTheDocument();
  });

  it("blocks management shell for non-business client contours", () => {
    useClientMock.mockReturnValue({
      client: {
        org: { id: "org-1", org_type: "INDIVIDUAL" },
        subscription: { plan_code: "CLIENT_START" },
        org_roles: ["CLIENT_OWNER"],
        user_roles: ["CLIENT_OWNER"],
        capabilities: [],
        nav_sections: [],
      },
    });
    useAuthMock.mockReturnValue({
      user: {
        token: "test.header.payload",
        roles: ["CLIENT_OWNER"],
      },
    });

    render(<ClientControlsPage />);

    expect(screen.getByText("Управление командой доступно только бизнес-клиентам с соответствующей ролью.")).toBeInTheDocument();
    expect(screen.queryByText("limits-content")).not.toBeInTheDocument();
  });
});

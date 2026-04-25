import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccessGate } from "./AccessGate";

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

describe("AccessGate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useClientJourneyMock.mockReturnValue({
      state: "AUTHENTICATED_UNCONNECTED",
      nextRoute: "/onboarding",
      draft: {},
      updateDraft: vi.fn(),
      resetDraft: vi.fn(),
      ensureRoute: vi.fn(),
    });
  });

  it("renders dashboard for demo client on /client/dashboard when portal/me is NEEDS_ONBOARDING", () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    useAuthMock.mockReturnValue({
      user: { email: "client@neft.local" },
    });
    useClientMock.mockReturnValue({
      client: {
        access_state: "NEEDS_ONBOARDING",
        user: { email: "client@neft.local" },
        org_roles: [],
        user_roles: [],
        capabilities: [],
      },
      isLoading: false,
      error: null,
      portalState: "READY",
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/client/dashboard"]}>
        <Routes>
          <Route
            path="/client/dashboard"
            element={
              <AccessGate title="Дашборд" capability="CLIENT_DASHBOARD">
                <div>Dashboard App Shell</div>
              </AccessGate>
            }
          />
          <Route path="/login" element={<div>LoginPage</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Dashboard App Shell")).toBeInTheDocument();
    expect(screen.queryByText("LoginPage")).not.toBeInTheDocument();
  });

  it("can disable demo bypass for owner routes that must respect real access state", () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    useAuthMock.mockReturnValue({
      user: { email: "client@neft.local" },
    });
    useClientMock.mockReturnValue({
      client: {
        access_state: "NEEDS_ONBOARDING",
        user: { email: "client@neft.local" },
        org_roles: [],
        user_roles: [],
        capabilities: [],
      },
      isLoading: false,
      error: null,
      portalState: "READY",
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/client/dashboard"]}>
        <Routes>
          <Route
            path="/client/dashboard"
            element={
              <AccessGate title="Дашборд" capability="CLIENT_DASHBOARD" allowDemoBypass={false}>
                <div>Dashboard App Shell</div>
              </AccessGate>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Подключить компанию")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard App Shell")).not.toBeInTheDocument();
  });

  it("keeps onboarding restriction for non-demo clients", () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");
    useAuthMock.mockReturnValue({
      user: { email: "client@corp.local" },
    });
    useClientMock.mockReturnValue({
      client: {
        access_state: "NEEDS_ONBOARDING",
        user: { email: "client@corp.local" },
        org_roles: [],
        user_roles: [],
        capabilities: [],
      },
      isLoading: false,
      error: null,
      portalState: "READY",
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/client/dashboard"]}>
        <Routes>
          <Route
            path="/client/dashboard"
            element={
              <AccessGate title="Дашборд" capability="CLIENT_DASHBOARD">
                <div>Dashboard App Shell</div>
              </AccessGate>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Подключить компанию")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard App Shell")).not.toBeInTheDocument();
  });

  it("does not treat canonical seeded client as showcase runtime when demo mode is disabled", () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");
    useAuthMock.mockReturnValue({
      user: { email: "client@neft.local" },
    });
    useClientMock.mockReturnValue({
      client: {
        access_state: "NEEDS_ONBOARDING",
        user: { email: "client@neft.local" },
        org_roles: [],
        user_roles: [],
        capabilities: [],
      },
      isLoading: false,
      error: null,
      portalState: "READY",
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/client/dashboard"]}>
        <Routes>
          <Route
            path="/client/dashboard"
            element={
              <AccessGate title="Дашборд" capability="CLIENT_DASHBOARD">
                <div>Dashboard App Shell</div>
              </AccessGate>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Подключить компанию")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard App Shell")).not.toBeInTheDocument();
  });


  it("Case A: onboarding CTA navigates once to /onboarding", () => {
    useAuthMock.mockReturnValue({
      user: { email: "client@corp.local" },
    });
    useClientMock.mockReturnValue({
      client: {
        access_state: "NEEDS_ONBOARDING",
        user: { email: "client@corp.local" },
        org_roles: [],
        user_roles: [],
        capabilities: [],
      },
      isLoading: false,
      error: null,
      portalState: "READY",
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route
            path="/dashboard"
            element={
              <AccessGate title="Дашборд" capability="CLIENT_DASHBOARD">
                <div>Dashboard App Shell</div>
              </AccessGate>
            }
          />
          <Route path="/onboarding" element={<div>Onboarding Route</div>} />
        </Routes>
      </MemoryRouter>,
    );

    const cta = screen.getByRole("link", { name: "Перейти к подключению" });
    fireEvent.click(cta);

    expect(screen.getByText("Onboarding Route")).toBeInTheDocument();
    expect(screen.queryByText("Подключить компанию")).not.toBeInTheDocument();
  });
});

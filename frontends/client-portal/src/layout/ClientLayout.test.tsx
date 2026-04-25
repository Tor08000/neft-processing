import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ClientLayout } from "./ClientLayout";

const useAuthMock = vi.fn();
const useClientMock = vi.fn();
const useClientJourneyMock = vi.fn();
const useLegalGateMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => useClientMock(),
}));

vi.mock("../auth/ClientJourneyContext", () => ({
  useClientJourney: () => useClientJourneyMock(),
}));

vi.mock("../auth/LegalGateContext", () => ({
  useLegalGate: () => useLegalGateMock(),
}));

vi.mock("../pwa/mode", () => ({
  isPwaMode: false,
}));

vi.mock("../lib/theme", () => ({
  getInitialTheme: () => "light",
  toggleTheme: () => "dark",
}));

vi.mock("@shared/demo/demo", () => ({
  isDemoClient: () => false,
}));

describe("ClientLayout mode routing", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useAuthMock.mockReturnValue({
      user: { email: "client@example.test" },
      logout: vi.fn(),
    });
    useLegalGateMock.mockReturnValue({
      isFeatureDisabled: false,
    });
  });

  it("exposes fleet routes from runtime workspace without a manual mode switcher", () => {
    useClientMock.mockReturnValue({
      client: {
        org: { id: "org-1", org_type: "LEGAL" },
        org_status: "ACTIVE",
        subscription: { plan_code: "CLIENT_BUSINESS" },
        modules: { fleet: { enabled: true }, logistics: { enabled: true } },
        entitlements_snapshot: { fleet: { enabled: true }, logistics: { enabled: true } },
        capabilities: ["CLIENT_FLEET"],
        nav_sections: [{ code: "fleet" }],
      },
    });
    useClientJourneyMock.mockReturnValue({
      state: "ACTIVE",
      draft: { customerType: "INDIVIDUAL" },
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route element={<ClientLayout pwaMode={false} />}>
            <Route path="/dashboard" element={<div>dashboard-screen</div>} />
            <Route path="/fleet/groups" element={<div>fleet-screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    const fleetLink = document.querySelector('a[href="/fleet/groups"]');
    expect(fleetLink).not.toBeNull();
    fireEvent.click(fleetLink as HTMLAnchorElement);

    expect(screen.getByText("fleet-screen")).toBeInTheDocument();
  });

  it("drops stale fleet mode back to dashboard when runtime no longer exposes fleet access", () => {
    window.localStorage.setItem("neft.client.mode", "fleet");
    useClientMock.mockReturnValue({
      client: {
        org: { id: "org-1", org_type: "INDIVIDUAL" },
        org_status: "ACTIVE",
        subscription: { plan_code: "CLIENT_START" },
        capabilities: [],
        nav_sections: [],
      },
    });
    useClientJourneyMock.mockReturnValue({
      state: "ACTIVE",
      draft: { customerType: "LEGAL_ENTITY" },
    });

    render(
      <MemoryRouter initialEntries={["/fleet/groups"]}>
        <Routes>
          <Route element={<ClientLayout pwaMode={false} />}>
            <Route path="/dashboard" element={<div>dashboard-screen</div>} />
            <Route path="/fleet/groups" element={<div>fleet-screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("dashboard-screen")).toBeInTheDocument();
  });

  it("promotes direct fleet-only routes into fleet mode when runtime workspace allows it", async () => {
    useClientMock.mockReturnValue({
      client: {
        org: { id: "org-1", org_type: "LEGAL" },
        org_status: "ACTIVE",
        subscription: { plan_code: "CLIENT_BUSINESS" },
        modules: { fleet: { enabled: true }, logistics: { enabled: true } },
        entitlements_snapshot: { fleet: { enabled: true }, logistics: { enabled: true } },
        capabilities: ["CLIENT_FLEET", "CLIENT_ANALYTICS"],
        nav_sections: [{ code: "fleet" }, { code: "analytics" }],
      },
    });
    useClientJourneyMock.mockReturnValue({
      state: "ACTIVE",
      draft: {},
    });

    render(
      <MemoryRouter initialEntries={["/analytics"]}>
        <Routes>
          <Route element={<ClientLayout pwaMode={false} />}>
            <Route path="/dashboard" element={<div>dashboard-screen</div>} />
            <Route path="/analytics" element={<div>analytics-screen</div>} />
            <Route path="/fleet/groups" element={<div>fleet-screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("analytics-screen")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    await waitFor(() => expect(window.localStorage.getItem("neft.client.mode")).toBe("fleet"));
    expect(screen.queryByText("dashboard-screen")).not.toBeInTheDocument();
  });

  it("keeps canonical /cases mounted as a deep-link support trail without exposing a separate nav item", () => {
    useClientMock.mockReturnValue({
      client: {
        org: { id: "org-1", org_type: "LEGAL" },
        org_status: "ACTIVE",
        subscription: { plan_code: "CLIENT_BUSINESS" },
        modules: { marketplace: { enabled: true }, support: { enabled: true }, documents: { enabled: true } },
        entitlements_snapshot: { marketplace: { enabled: true }, support: { enabled: true }, documents: { enabled: true } },
        capabilities: ["MARKETPLACE"],
        nav_sections: [{ code: "marketplace" }, { code: "support" }, { code: "documents" }],
      },
    });
    useClientJourneyMock.mockReturnValue({
      state: "ACTIVE",
      draft: { customerType: "LEGAL_ENTITY" },
    });

    render(
      <MemoryRouter initialEntries={["/cases/case-1"]}>
        <Routes>
          <Route element={<ClientLayout pwaMode={false} />}>
            <Route path="/dashboard" element={<div>dashboard-screen</div>} />
            <Route path="/client/support" element={<div>support-screen</div>} />
            <Route path="/cases/:id" element={<div>case-screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("case-screen")).toBeInTheDocument();
    const supportLink = document.querySelector('a[href="/client/support"]');
    expect(supportLink).not.toBeNull();
    expect(supportLink?.className).toContain("neftc-nav-item--active");
    expect(document.querySelector('a[href="/cases"]')).toBeNull();
  });
});

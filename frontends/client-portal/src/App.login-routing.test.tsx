import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { AuthSession } from "./api/types";

vi.mock("./pages/MarketplaceOrderDetailsPage", () => ({
  MarketplaceOrderDetailsPage: () => <div>marketplace-order-detail-screen</div>,
}));

vi.mock("./pages/DashboardPage", () => ({
  DashboardPage: () => <div>dashboard-screen</div>,
}));

vi.mock("./pages/OnboardingPage", () => ({
  OnboardingPage: () => <div>onboarding-screen</div>,
}));

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@example.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 60_000,
};

describe("client auth-entry compatibility routing", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("preserves marketplace order returnUrl across the /client/login compatibility alias", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes("/portal/me")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                user: { id: "u-1", email: "client@example.test" },
                org: { id: "org-1", name: "NEFT Client", org_type: "LEGAL", status: "ACTIVE" },
                org_status: "ACTIVE",
                org_roles: ["CLIENT_OWNER"],
                user_roles: ["CLIENT_OWNER"],
                roles: ["CLIENT_OWNER"],
                capabilities: ["MARKETPLACE", "CLIENT_DASHBOARD"],
                nav_sections: [{ code: "marketplace", label: "Marketplace" }],
                modules: { dashboard: { enabled: true } },
                features: { onboarding_enabled: true, legal_gate_enabled: false },
                access_state: "ACTIVE",
                access_reason: null,
              }),
              { status: 200 },
            ),
          );
        }
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }) as unknown as typeof fetch,
    );

    render(
      <MemoryRouter initialEntries={["/client/login?returnUrl=%2Fmarketplace%2Forders%2Forder-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("marketplace-order-detail-screen")).toBeInTheDocument();
    expect(screen.queryByText("dashboard-screen")).not.toBeInTheDocument();
    expect(screen.queryByText("onboarding-screen")).not.toBeInTheDocument();
  });

  it("restores a persisted session snapshot on cold marketplace order deep-links", async () => {
    window.localStorage.setItem(
      "neft_client_access_token",
      JSON.stringify({
        token: session.token,
        refreshToken: session.refreshToken,
        email: session.email,
        roles: session.roles,
        subjectType: session.subjectType,
        clientId: session.clientId,
        expiresAt: session.expiresAt,
      }),
    );

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes("/portal/me")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                user: { id: "u-1", email: "client@example.test" },
                org: { id: "org-1", name: "NEFT Client", org_type: "LEGAL", status: "ACTIVE" },
                org_status: "ACTIVE",
                org_roles: ["CLIENT_OWNER"],
                user_roles: ["CLIENT_OWNER"],
                roles: ["CLIENT_OWNER"],
                capabilities: ["MARKETPLACE", "CLIENT_DASHBOARD"],
                nav_sections: [{ code: "marketplace", label: "Marketplace" }],
                modules: { dashboard: { enabled: true } },
                features: { onboarding_enabled: true, legal_gate_enabled: false },
                access_state: "ACTIVE",
                access_reason: null,
              }),
              { status: 200 },
            ),
          );
        }
        if (url.includes("/api/v1/auth/me")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                email: "client@example.test",
                roles: ["CLIENT_OWNER"],
                subject_type: "CLIENT",
                client_id: "client-1",
              }),
              { status: 200 },
            ),
          );
        }
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }) as unknown as typeof fetch,
    );

    render(
      <MemoryRouter initialEntries={["/marketplace/orders/order-1"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("marketplace-order-detail-screen")).toBeInTheDocument();
    expect(screen.queryByText("dashboard-screen")).not.toBeInTheDocument();
    expect(screen.queryByText("onboarding-screen")).not.toBeInTheDocument();
  });
});

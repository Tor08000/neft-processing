import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { AuthSession } from "./api/types";
import type { CustomerType } from "@shared/subscriptions/catalog";

vi.mock("./pages/BalancesPage", () => ({
  BalancesPage: () => <div>balances-screen</div>,
}));

vi.mock("./pages/ClientControlsPage", () => ({
  ClientControlsPage: () => <h1>management-screen</h1>,
}));

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@example.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 60_000,
};

const buildPortalPayload = (orgType: "INDIVIDUAL" | "LEGAL") => ({
  user: { id: "u-1", email: "client@example.test" },
  org: { id: "org-1", name: "ООО Нефт Тест", org_type: orgType, status: "ACTIVE" },
  org_status: "ACTIVE",
  org_roles: ["CLIENT_OWNER"],
  user_roles: ["CLIENT_OWNER"],
  capabilities: ["CLIENT_BILLING", "CLIENT_DASHBOARD"],
  nav_sections: [],
  modules: { analytics: { enabled: true } },
  features: { onboarding_enabled: true, legal_gate_enabled: false },
  access_state: "ACTIVE",
});

const seedActiveJourneyDraft = (customerType: CustomerType) => {
  window.localStorage.setItem(
    "neft_client_journey_draft",
    JSON.stringify({
      selectedPlan: customerType === "INDIVIDUAL" ? "CLIENT_START" : "CLIENT_BUSINESS",
      customerType,
      profileCompleted: true,
      documentsByCode: { service_agreement: "reviewed", onboarding_ack: "reviewed" },
      documentsSigned: true,
      signAccepted: true,
      subscriptionState: "ACTIVE",
    }),
  );
};

describe("client workspace route gating", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("blocks finance routes for individual clients even when the draft looks business-ready", async () => {
    seedActiveJourneyDraft("LEGAL_ENTITY");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes("/portal/me")) {
          return Promise.resolve(new Response(JSON.stringify(buildPortalPayload("INDIVIDUAL")), { status: 200 }));
        }
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }) as unknown as typeof fetch,
    );

    render(
      <MemoryRouter initialEntries={["/balances"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("Финансовый контур доступен только бизнес-клиентам."),
    ).toBeInTheDocument();
    expect(screen.queryByText("balances-screen")).not.toBeInTheDocument();
  });

  it("blocks management routes for non-business clients even when the draft looks business-ready", async () => {
    seedActiveJourneyDraft("LEGAL_ENTITY");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes("/portal/me")) {
          return Promise.resolve(new Response(JSON.stringify(buildPortalPayload("INDIVIDUAL")), { status: 200 }));
        }
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }) as unknown as typeof fetch,
    );

    render(
      <MemoryRouter initialEntries={["/settings/management"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("Управление командой доступно только бизнес-клиентам с соответствующей ролью."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "management-screen" })).not.toBeInTheDocument();
  });

  it("keeps management routes available for business clients even when the draft still looks individual", async () => {
    seedActiveJourneyDraft("INDIVIDUAL");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = input.toString();
        if (url.includes("/portal/me")) {
          return Promise.resolve(new Response(JSON.stringify(buildPortalPayload("LEGAL")), { status: 200 }));
        }
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }) as unknown as typeof fetch,
    );

    render(
      <MemoryRouter initialEntries={["/settings/management"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "management-screen" })).toBeInTheDocument();
  });
});

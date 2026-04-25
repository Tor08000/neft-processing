import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";

vi.mock("./OnboardingPage", () => ({
  OnboardingPage: () => {
    const location = useLocation();
    return <div>Onboarding Route: {location.pathname}</div>;
  },
}));

import { App } from "../App";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@corp.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const portalMePayload = {
  user: { id: "u-1", email: "client@corp.test" },
  org: { id: "org-1", name: "ООО Тест", org_type: "LEGAL", status: "ONBOARDING" },
  org_status: "ONBOARDING",
  org_roles: ["CLIENT_OWNER"],
  user_roles: ["CLIENT_OWNER"],
  capabilities: [],
  nav_sections: [],
  modules: {},
  features: { onboarding_enabled: true, legal_gate_enabled: false },
  access_state: "NEEDS_ONBOARDING",
};

describe("Connect flow compatibility routing", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function stubFetch() {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/portal/me")) {
        return Promise.resolve(new Response(JSON.stringify(portalMePayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
  }

  it("redirects /connect to canonical onboarding", async () => {
    stubFetch();

    render(
      <MemoryRouter initialEntries={["/connect"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Onboarding Route: /onboarding")).toBeInTheDocument();
  });

  it("redirects /connect/plan to canonical onboarding plan", async () => {
    stubFetch();

    render(
      <MemoryRouter initialEntries={["/connect/plan"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Onboarding Route: /onboarding/plan")).toBeInTheDocument();
  });

  it("redirects contract-shaped connect tails to canonical onboarding contract", async () => {
    stubFetch();

    render(
      <MemoryRouter initialEntries={["/connect/sign"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Onboarding Route: /onboarding/contract")).toBeInTheDocument();
  });
});

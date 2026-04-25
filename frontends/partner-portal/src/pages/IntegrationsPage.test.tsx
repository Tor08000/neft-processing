import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession, PortalMeResponse } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "owner@neft.local",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const portalMe: PortalMeResponse = {
  user: {
    id: "user-1",
    email: session.email,
    subject_type: session.subjectType,
  },
  org_roles: ["PARTNER"],
  user_roles: ["PARTNER_OWNER"],
  capabilities: ["PARTNER_FINANCE_VIEW"],
  access_state: "ACTIVE",
  gating: {
    onboarding_enabled: false,
    legal_gate_enabled: false,
  },
  partner: {
    kind: "FINANCE_PARTNER",
    partner_role: "OWNER",
    partner_roles: ["OWNER"],
    default_route: "/finance",
    workspaces: [
      { code: "finance", label: "Finance", default_route: "/finance" },
      { code: "support", label: "Support", default_route: "/support/requests" },
      { code: "profile", label: "Profile", default_route: "/partner/profile" },
    ],
  },
};

let webhookRequested = false;

const mockFetch = (url: string) => {
  if (url.includes("/api/int/v1/webhooks/")) {
    webhookRequested = true;
  }
  if (url.includes("/partner/auth/verify")) {
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } });
  }
  if (url.includes("/portal/me")) {
    return new Response(JSON.stringify(portalMe), { status: 200, headers: { "content-type": "application/json" } });
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "content-type": "application/json" } });
};

beforeEach(() => {
  webhookRequested = false;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Integrations route topology", () => {
  it("keeps /integrations unmounted in the partner shell", async () => {
    render(
      <MemoryRouter initialEntries={["/integrations"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Страница не найдена")).toBeInTheDocument();
    expect(webhookRequested).toBe(false);
  });
});

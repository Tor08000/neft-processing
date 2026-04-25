import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession, PortalMeResponse } from "../api/types";
import i18n from "../i18n";

const session: AuthSession = {
  token: "token-1",
  email: "operator@demo.test",
  roles: ["PARTNER_OPERATOR"],
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
  user_roles: ["PARTNER_OPERATOR"],
  capabilities: ["PARTNER_CORE"],
  access_state: "ACTIVE",
  gating: {
    onboarding_enabled: false,
    legal_gate_enabled: false,
  },
  partner: {
    kind: "SERVICE_PARTNER",
    partner_role: "OPERATOR",
    partner_roles: ["OPERATOR"],
    default_route: "/services",
    workspaces: [
      { code: "services", label: "Services", default_route: "/services" },
      { code: "support", label: "Support", default_route: "/support/requests" },
      { code: "profile", label: "Profile", default_route: "/partner/profile" },
    ],
  },
};

const mockFetch = (url: string) => {
  if (url.includes("/partner/auth/verify")) {
    return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } });
  }
  if (url.includes("/portal/me")) {
    return new Response(JSON.stringify(portalMe), { status: 200, headers: { "content-type": "application/json" } });
  }
  if (url.includes("/partner/services")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "service-1",
            title: "Мойка",
            description: "Полный комплекс",
            category: "Автомойка",
            status: "ACTIVE",
            duration_min: 60,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      { status: 200 },
    );
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200 });
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Services role gating", () => {
  it("hides create/import/activate actions for non-managers", async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/services"]}>
          <App initialSession={session} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByText(/Каталог услуг/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Создать$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Редактировать$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Активировать$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Отключить$/ })).not.toBeInTheDocument();
  });
});

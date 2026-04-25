import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const TEST_ACCESS_TOKEN = "test.header.payload";

const session: AuthSession = {
  token: TEST_ACCESS_TOKEN,
  email: "client@corp.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const dashboardPayload = {
  role: "OWNER",
  timezone: "Europe/Moscow",
  widgets: [
    { type: "kpi", key: "total_spend_30d", data: { value: 125000, currency: "RUB" } },
    { type: "cta", key: "owner_actions", data: null },
  ],
};

const portalMePayload = {
  user: { id: "u-1", email: "client@corp.test" },
  org: { id: "org-1", name: "ООО Тест", org_type: "LEGAL", status: "ACTIVE" },
  org_status: "ACTIVE",
  org_roles: ["CLIENT_OWNER"],
  user_roles: ["CLIENT_OWNER"],
  capabilities: ["CLIENT_DASHBOARD", "MARKETPLACE"],
  nav_sections: [],
  modules: { analytics: { enabled: true } },
  features: { onboarding_enabled: true, legal_gate_enabled: false },
  access_state: "ACTIVE",
};

describe("Client portal pages", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("renders dashboard without crashing", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");

    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/portal/me")) {
        return Promise.resolve(new Response(JSON.stringify(portalMePayload), { status: 200 }));
      }
      if (url.includes("/client/dashboard")) {
        return Promise.resolve(new Response(JSON.stringify(dashboardPayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: /Рабочий стол/i })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: /Общие расходы/i })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: /Следующие шаги владельца/i })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Создать отчёт/i })).toBeInTheDocument();
  });
});

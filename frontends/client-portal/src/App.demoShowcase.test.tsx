import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "./api/types";

vi.mock("./pages/OverviewPage", () => ({ OverviewPage: () => <div>Overview Mock</div> }));
vi.mock("./pages/DocumentsPage", () => ({ DocumentsPage: () => <div>Documents Mock</div> }));
vi.mock("./pages/ReportsPage", () => ({ ReportsPage: () => <div>Reports Mock</div> }));
vi.mock("./pages/LimitTemplatesPage", () => ({ LimitTemplatesPage: () => <div>Limits Mock</div> }));
vi.mock("./pages/SettingsPage", () => ({ SettingsPage: () => <div>Settings Mock</div> }));
vi.mock("./pages/FleetGroupsPage", () => ({ FleetGroupsPage: () => <div>Fleet Groups Mock</div> }));
vi.mock("./pages/AnalyticsDashboardPage", () => ({ AnalyticsDashboardPage: () => <div>Analytics Mock</div> }));

import { App } from "./App";

const demoSession: AuthSession = {
  token: "demo-token",
  email: "client@neft.local",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-demo",
  expiresAt: Date.now() + 60 * 60 * 1000,
};

const portalMePayload = {
  user: { id: "u-demo", email: "client@neft.local" },
  org: null,
  org_status: null,
  org_roles: [],
  user_roles: [],
  capabilities: [],
  nav_sections: [],
  modules: {},
  features: {},
  access_state: "NEEDS_ONBOARDING",
};

const routeCases = [
  { path: "/client/dashboard", marker: "Overview Mock" },
  { path: "/client/documents", marker: "Documents Mock" },
  { path: "/client/reports", marker: "Reports Mock" },
  { path: "/client/limits", marker: "Limits Mock" },
  { path: "/client/settings", marker: "Settings Mock" },
  { path: "/fleet/groups", marker: "Fleet Groups Mock" },
  { path: "/analytics", marker: "Analytics Mock" },
];

describe("Demo showcase navigation", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it.each(routeCases)("keeps full demo navigation and route access for $path", async ({ path, marker }) => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/portal/me")) {
        return Promise.resolve(new Response(JSON.stringify(portalMePayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={[path]}>
        <App initialSession={demoSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(marker)).toBeInTheDocument();
    expect(screen.getAllByText("Документы").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Аналитика").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Лимиты").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Автопарк").length).toBeGreaterThan(0);

    expect(screen.queryByText("Подключить компанию")).not.toBeInTheDocument();
    expect(screen.queryByText("Требуется авторизация")).not.toBeInTheDocument();
  });
});

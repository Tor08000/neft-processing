import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import { FleetPoliciesPage } from "./FleetPoliciesPage";

const adminSession: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const viewerSession: AuthSession = {
  token: "test.fleet.viewer",
  email: "viewer@demo.test",
  roles: ["CLIENT_USER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("FleetPoliciesPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders policies list", async () => {
    window.sessionStorage.clear();
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/policies")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: "policy-1",
                  scope_type: "GROUP",
                  scope_id: "group-1",
                  group_name: "Logistics",
                  trigger_type: "LIMIT_BREACH",
                  severity_min: "HIGH",
                  breach_kind: "HARD",
                  action: "NOTIFY_ONLY",
                  cooldown_seconds: 300,
                  status: "ACTIVE",
                  created_at: new Date().toISOString(),
                },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      if (url.includes("/client/fleet/groups")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/cards")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/policies"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={adminSession}>
            <FleetPoliciesPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Logistics")).toBeInTheDocument();
  });

  it("validates create modal required fields", async () => {
    window.sessionStorage.clear();
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/policies")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/groups")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/cards")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/policies"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={adminSession}>
            <FleetPoliciesPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    const openButton = await screen.findByRole("button", { name: /Создать политику/i });
    await userEvent.click(openButton);

    const submitButtons = screen.getAllByRole("button", { name: /Создать политику/i });
    await userEvent.click(submitButtons[submitButtons.length - 1]);

    expect(await screen.findByText(/Заполните обязательные поля/i)).toBeInTheDocument();
  });

  it("hides create button for viewer", async () => {
    window.sessionStorage.clear();
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/policies")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/groups")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/cards")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/policies"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={viewerSession}>
            <FleetPoliciesPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Политик пока нет/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Создать политику/i })).not.toBeInTheDocument();
  });

  it("shows create button for admin", async () => {
    window.sessionStorage.clear();
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/policies")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/groups")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/cards")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/policies"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={adminSession}>
            <FleetPoliciesPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: /Создать политику/i })).toBeInTheDocument();
  });
});

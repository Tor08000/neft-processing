import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import { FleetPolicyExecutionsPage } from "./FleetPolicyExecutionsPage";

const adminSession: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("FleetPolicyExecutionsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders executions table", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/policies/executions")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  executed_at: new Date().toISOString(),
                  policy_id: "policy-1",
                  scope_type: "CARD",
                  scope_id: "card-1",
                  card_alias: "Driver 1",
                  trigger_type: "LIMIT_BREACH",
                  severity: "HIGH",
                  action: "AUTO_BLOCK_CARD",
                  status: "APPLIED",
                  reason: "Hard breach above limit",
                  audit_event_id: "event-1",
                },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/policies/executions"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={adminSession}>
            <FleetPolicyExecutionsPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Driver 1/i)).toBeInTheDocument();
    const actionLabels = await screen.findAllByText(/Автоблокировка карты/i);
    expect(actionLabels.length).toBeGreaterThan(0);
  });

  it("renders filters", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/policies/executions")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/policies/executions"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={adminSession}>
            <FleetPolicyExecutionsPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText("С")).toBeInTheDocument();
    expect(screen.getByLabelText("По")).toBeInTheDocument();
    expect(screen.getByLabelText("Статус")).toBeInTheDocument();
    expect(screen.getByLabelText("Триггер")).toBeInTheDocument();
  });
});

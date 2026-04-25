import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import { FleetNotificationsPage } from "./FleetNotificationsPage";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("FleetNotificationsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders alerts list", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/notifications/alerts")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: "alert-1",
                  status: "OPEN",
                  severity: "HIGH",
                  type: "LIMIT_BREACH",
                  summary: "Spike detected",
                  scope_type: "CARD",
                  card_alias: "Driver 1",
                  occurred_at: new Date().toISOString(),
                },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      if (url.includes("/client/fleet/notifications/channels")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [{ id: "channel-1", channel_type: "EMAIL" }] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/notifications"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={session}>
            <FleetNotificationsPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Spike detected")).toBeInTheDocument();
  });

  it("acks alert", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/notifications/alerts/alert-1/ack")) {
        return Promise.resolve(new Response(JSON.stringify({ id: "alert-1", status: "ACKED" }), { status: 200 }));
      }
      if (url.includes("/client/fleet/notifications/alerts")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: "alert-1",
                  status: "OPEN",
                  severity: "HIGH",
                  type: "LIMIT_BREACH",
                  summary: "Spike detected",
                  scope_type: "CARD",
                  card_alias: "Driver 1",
                  occurred_at: new Date().toISOString(),
                },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      if (url.includes("/client/fleet/notifications/channels")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [{ id: "channel-1", channel_type: "EMAIL" }] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/notifications"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={session}>
            <FleetNotificationsPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    const ackButton = await screen.findByRole("button", { name: /Подтвердить/i });
    await userEvent.click(ackButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/client/fleet/notifications/alerts/alert-1/ack"), expect.anything());
    });
  });
});

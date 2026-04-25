import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import { FleetNotificationPoliciesPage } from "./FleetNotificationPoliciesPage";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("FleetNotificationPoliciesPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("validates create policy modal", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/notifications/policies")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/notifications/channels")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/cards")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/groups")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/notifications/policies"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={session}>
            <FleetNotificationPoliciesPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    const openButton = await screen.findByRole("button", { name: /Создать политику/i });
    await userEvent.click(openButton);

    const dialog = await screen.findByRole("dialog");
    const submitButton = within(dialog).getByRole("button", { name: /^Создать$/i });
    await userEvent.click(submitButton);

    expect(await screen.findByText(/Заполните обязательные поля/i)).toBeInTheDocument();
  });
});

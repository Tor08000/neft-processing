import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import { FleetGroupDetailsPage } from "./FleetGroupDetailsPage";

const session: AuthSession = {
  token: "test.header.payload",
  email: "viewer@demo.test",
  roles: ["CLIENT_USER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("FleetGroupDetailsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders tabs and hides admin actions for viewer", async () => {
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = input.toString();
      if (url.includes("/client/fleet/groups") && init?.method !== "POST") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [{ id: "group-1", name: "Group A", description: "Demo" }],
            }),
            { status: 200 },
          ),
        );
      }
      if (url.includes("/client/fleet/cards")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                { id: "card-1", card_alias: "Card A", masked_pan: "123456******7890" },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      if (url.includes("/client/fleet/groups/group-1/access")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/employees")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ items: [{ id: "emp-1", email: "viewer@demo.test", status: "ACTIVE" }] }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/groups/group-1"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={session}>
            <Routes>
              <Route path="/fleet/groups/:id" element={<FleetGroupDetailsPage />} />
            </Routes>
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: /Карты/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Доступы/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Лимиты/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Расходы/i })).toBeInTheDocument();

    const accessTab = screen.getByRole("button", { name: /Доступы/i });
    await userEvent.click(accessTab);

    expect(screen.queryByRole("button", { name: /Выдать доступ/i })).not.toBeInTheDocument();
  });
});

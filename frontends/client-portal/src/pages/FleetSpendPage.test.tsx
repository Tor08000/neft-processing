import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import { FleetSpendPage } from "./FleetSpendPage";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("FleetSpendPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders filters and triggers export", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/groups")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [{ id: "group-1", name: "Group A" }] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/cards")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [{ id: "card-1", card_alias: "Card A" }] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/transactions/export")) {
        return Promise.resolve(new Response(JSON.stringify({ url: "https://export.test/file.csv", expires_in: 600 }), { status: 200 }));
      }
      if (url.includes("/client/fleet/spend/summary")) {
        return Promise.resolve(new Response(JSON.stringify({ group_by: "category", rows: [] }), { status: 200 }));
      }
      if (url.includes("/client/fleet/transactions")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/spend"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={session}>
            <FleetSpendPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Fleet · Spend/i)).toBeInTheDocument();
    expect(await screen.findByText(/Группа/i)).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Card A" })).toBeInTheDocument();

    const exportButton = screen.getByRole("button", { name: /Экспорт CSV/i });
    await userEvent.click(exportButton);

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/client/fleet/transactions/export"), expect.anything()),
    );
    await waitFor(() => expect(openSpy).toHaveBeenCalledWith("https://export.test/file.csv", "_blank", "noopener"));
  });
});

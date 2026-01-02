import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
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
  });

  it("renders filters and triggers export", async () => {
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
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Fleet · Spend/i)).toBeInTheDocument();
    expect(screen.getByText(/Группа/i)).toBeInTheDocument();
    expect(screen.getByText(/Карта/i)).toBeInTheDocument();

    const exportButton = screen.getByRole("button", { name: /Экспорт CSV/i });
    await userEvent.click(exportButton);

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/client/fleet/transactions/export"), expect.anything()),
    );
  });
});

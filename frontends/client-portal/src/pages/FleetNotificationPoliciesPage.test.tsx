import { render, screen, within } from "@testing-library/react";
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

describe("FleetNotificationPoliciesPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
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
        <App initialSession={session} />
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

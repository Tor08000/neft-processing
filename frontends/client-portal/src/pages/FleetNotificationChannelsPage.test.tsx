import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("FleetNotificationChannelsPage", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("validates create channel modal", async () => {
    window.localStorage.setItem("neft.client.mode", "fleet");
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/notifications/channels")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/notifications/channels"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    const openButton = await screen.findByRole("button", { name: /Создать канал/i });
    await userEvent.click(openButton);

    const dialog = await screen.findByRole("dialog");
    const submitButton = within(dialog).getByRole("button", { name: /^Создать$/i });
    await userEvent.click(submitButton);

    expect(await screen.findByText(/Укажите target/i)).toBeInTheDocument();
  });
});

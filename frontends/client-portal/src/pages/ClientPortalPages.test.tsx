import { render, screen } from "@testing-library/react";
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

const dashboardPayload = {
  role: "OWNER",
  timezone: "Europe/Moscow",
  widgets: [
    { type: "kpi", key: "total_spend_30d", data: { value: 125000, currency: "RUB" } },
    { type: "cta", key: "owner_actions", data: null },
  ],
};

describe("Client portal pages", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders dashboard without crashing", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/dashboard")) {
        return Promise.resolve(new Response(JSON.stringify(dashboardPayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Общие расходы/i)).toBeInTheDocument();
    expect(screen.getByText(/Создать отчёт/i)).toBeInTheDocument();
  });
});

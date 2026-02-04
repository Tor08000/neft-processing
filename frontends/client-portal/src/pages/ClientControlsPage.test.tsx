import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const adminSession: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_ADMIN"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const readOnlySession: AuthSession = {
  token: "token-2",
  email: "client.readonly@demo.test",
  roles: ["CLIENT_USER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const buildFetchMock = () =>
  vi.fn((input: RequestInfo) => {
    const url = input.toString();
    if (url.includes("/client/limits")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            amount_limits: [],
            operation_limits: [],
            service_limits: [],
            partner_limits: [],
            station_limits: [],
          }),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/client/users")) {
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    }
    if (url.includes("/client/services")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [
              {
                id: "service-1",
                partner: "Demo partner",
                service: "Fuel",
                status: "ENABLED",
                restrictions: "—",
              },
            ],
          }),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/client/features")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [
              {
                key: "feature-1",
                description: "Feature",
                status: "ON",
                scope: "client",
              },
            ],
          }),
          { status: 200 },
        ),
      );
    }
    return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
  });

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

beforeEach(() => {
  (import.meta.env as Record<string, string>).VITE_API_BASE = "http://gateway";
});

describe("Client controls", () => {
  it("renders each management tab", async () => {
    const fetchMock = buildFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/settings/management"]}>
        <App initialSession={adminSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Лимиты" })).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Пользователи" }));
    expect(await screen.findByRole("heading", { name: "Пользователи" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Добавить пользователя" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Услуги и партнёры" }));
    expect(await screen.findByRole("heading", { name: "Услуги и партнёры" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Возможности" }));
    expect(await screen.findByRole("heading", { name: "Возможности" })).toBeInTheDocument();
  });

  it("disables actions for read-only users", async () => {
    const fetchMock = buildFetchMock();
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/settings/management"]}>
        <App initialSession={readOnlySession} />
      </MemoryRouter>,
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Пользователи" }));

    expect(await screen.findByRole("button", { name: "Добавить пользователя" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Услуги и партнёры" }));
    expect(await screen.findByRole("button", { name: "Отключить" })).toBeDisabled();
  });

  it("renders error state for failed loads", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/limits")) {
        return Promise.resolve(new Response("Boom", { status: 500 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/settings/management"]}>
        <App initialSession={adminSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Не удалось выполнить запрос")).toBeInTheDocument();
  });
});

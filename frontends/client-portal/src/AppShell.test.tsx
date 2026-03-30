import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { AuthSession } from "./api/types";

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_USER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const emptyResponse = new Response(JSON.stringify({ items: [] }), { status: 200 });

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(emptyResponse)) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Client portal shell", () => {
  it("renders client layout and primary navigation", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Клиентский портал/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Обзор/i })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Документы/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /Настройки/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /Пользователи/i }).length).toBeGreaterThan(0);
  });

  it("blocks operations for read-only users", async () => {
    render(
      <MemoryRouter initialEntries={["/operations"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Недостаточно прав/)).toBeInTheDocument();
  });

  it("loads cards and allows blocking", async () => {
    const cardsPayload = {
      items: [
        { id: "card-1", pan_masked: "1111", status: "ACTIVE", limits: [] },
        { id: "card-2", pan_masked: "2222", status: "BLOCKED", limits: [] },
      ],
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(cardsPayload), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "BLOCKED" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <MemoryRouter initialEntries={["/cards"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("card-1")).toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: /Заблокировать/i })[0]);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/cards/card-1"), expect.objectContaining({ method: "PATCH" })));
    await waitFor(() => expect(screen.getAllByText(/BLOCKED/)).not.toHaveLength(0));
  });
});

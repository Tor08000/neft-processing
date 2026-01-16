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

describe("Support tickets list", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders empty state", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify({ items: [], next_cursor: null }), { status: 200 })),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/client/support"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Обращений пока нет")).toBeInTheDocument();
  });

  it("renders list rows", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            items: [
              {
                id: "ticket-1",
                org_id: "client-1",
                created_by_user_id: "user-1",
                subject: "Проблема с лимитами",
                message: "Описание",
                status: "OPEN",
                priority: "NORMAL",
                created_at: "2025-01-01T10:00:00Z",
                updated_at: "2025-01-01T10:05:00Z",
              },
            ],
            next_cursor: null,
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/client/support"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Проблема с лимитами")).toBeInTheDocument();
    expect(screen.getByText("Открыто")).toBeInTheDocument();
  });
});

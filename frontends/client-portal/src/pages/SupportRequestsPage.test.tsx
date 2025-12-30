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

describe("Support requests list", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders empty state", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), { status: 200 }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/support/requests"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("У вас пока нет обращений.")).toBeInTheDocument();
  });

  it("renders list rows", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            items: [
              {
                id: "sr-1",
                tenant_id: 1,
                client_id: "client-1",
                partner_id: null,
                created_by_user_id: "user-1",
                scope_type: "CLIENT",
                subject_type: "ORDER",
                subject_id: "order-1",
                correlation_id: null,
                event_id: null,
                title: "Проблема с заказом",
                description: "Описание",
                status: "OPEN",
                priority: "NORMAL",
                created_at: "2025-01-01T10:00:00Z",
                updated_at: "2025-01-01T10:05:00Z",
                resolved_at: null,
              },
            ],
            total: 1,
            limit: 50,
            offset: 0,
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/support/requests"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Проблема с заказом")).toBeInTheDocument();
    expect(screen.getByText("Открыто")).toBeInTheDocument();
  });
});

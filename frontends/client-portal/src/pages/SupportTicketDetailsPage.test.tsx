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

describe("Support ticket details", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders detail view", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            id: "ticket-1",
            org_id: "client-1",
            created_by_user_id: "user-1",
            subject: "Проблема с документом",
            message: "Документ не подписывается",
            status: "IN_PROGRESS",
            priority: "NORMAL",
            created_at: "2025-01-01T10:00:00Z",
            updated_at: "2025-01-01T10:05:00Z",
            comments: [
              { user_id: "user-2", message: "Нужен скрин", created_at: "2025-01-01T11:00:00Z" },
            ],
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/client/support/ticket-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Проблема с документом")).toBeInTheDocument();
    expect(screen.getByText("В работе")).toBeInTheDocument();
    expect(screen.getByText("Документ не подписывается")).toBeInTheDocument();
    expect(screen.getByText("Нужен скрин")).toBeInTheDocument();
  });
});

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

describe("Support request details", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders detail view", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            id: "sr-1",
            tenant_id: 1,
            client_id: "client-1",
            partner_id: null,
            created_by_user_id: "user-1",
            scope_type: "CLIENT",
            subject_type: "DOCUMENT",
            subject_id: "doc-1",
            correlation_id: "corr-1",
            event_id: null,
            title: "Проблема с документом",
            description: "Документ не подписывается",
            status: "IN_PROGRESS",
            priority: "NORMAL",
            created_at: "2025-01-01T10:00:00Z",
            updated_at: "2025-01-01T10:05:00Z",
            resolved_at: null,
            timeline: [
              { status: "OPEN", occurred_at: "2025-01-01T10:00:00Z" },
              { status: "IN_PROGRESS", occurred_at: "2025-01-01T11:00:00Z" },
            ],
          }),
          { status: 200 },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/support/requests/sr-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Проблема с документом")).toBeInTheDocument();
    expect(screen.getByText("В работе")).toBeInTheDocument();
    expect(screen.getByText("Документ не подписывается")).toBeInTheDocument();
  });
});

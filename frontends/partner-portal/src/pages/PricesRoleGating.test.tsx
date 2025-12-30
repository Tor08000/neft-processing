import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "operator@demo.test",
  roles: ["PARTNER_OPERATOR"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const mockFetch = (url: string) => {
  if (url.includes("/partner/prices/versions/") && !url.endsWith("/versions")) {
    return new Response(
      JSON.stringify({
        id: "version-1",
        partner_id: "partner-1",
        station_scope: "all",
        status: "PUBLISHED",
        created_at: new Date().toISOString(),
        active: true,
        item_count: 10,
        error_count: 0,
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/prices/versions")) {
    return new Response(JSON.stringify({ items: [] }), { status: 200 });
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200 });
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Prices role gating", () => {
  it("hides publish and rollback actions for non-owners", async () => {
    render(
      <MemoryRouter initialEntries={["/prices/version-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Версия/)).toBeInTheDocument();
    expect(screen.queryByText(/Публиковать/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Rollback/)).not.toBeInTheDocument();
  });
});

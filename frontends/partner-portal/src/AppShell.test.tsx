import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { AuthSession } from "./api/types";

const session: AuthSession = {
  token: "token-1",
  email: "partner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
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

describe("Partner portal shell", () => {
  it("renders partner layout with navigation", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Partner Portal/i)).toBeInTheDocument();
    expect(screen.getByText(/АЗС/)).toBeInTheDocument();
    expect(screen.getByText(/Выплаты/)).toBeInTheDocument();
  });

  it("mounts dashboard and payouts pages", async () => {
    render(
      <MemoryRouter initialEntries={["/payouts"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Выплаты/)).toBeInTheDocument();
  });
});

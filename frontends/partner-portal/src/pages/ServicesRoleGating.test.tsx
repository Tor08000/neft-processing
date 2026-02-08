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
  if (url.includes("/partner/services")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "service-1",
            title: "Мойка",
            description: "Полный комплекс",
            category: "Автомойка",
            status: "ACTIVE",
            duration_min: 60,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
      { status: 200 },
    );
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

describe("Services role gating", () => {
  it("hides create/import/activate actions for non-managers", async () => {
    render(
      <MemoryRouter initialEntries={["/services"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Каталог услуг/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Создать услугу/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Submit/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Archive/ })).not.toBeInTheDocument();
  });
});

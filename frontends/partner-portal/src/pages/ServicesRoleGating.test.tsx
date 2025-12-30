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
  if (url.includes("/partner/catalog")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "catalog-1",
            kind: "SERVICE",
            title: "Мойка",
            description: "Полный комплекс",
            category: "Автомойка",
            baseUom: "услуга",
            status: "ACTIVE",
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            activeOffersCount: 1,
          },
        ],
        page: 1,
        pageSize: 10,
        total: 1,
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

    expect(await screen.findByText(/Каталог услуг и товаров/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Создать/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Preview/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Apply import/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Activate/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Disable/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Импорт недоступен/)).toBeInTheDocument();
  });
});

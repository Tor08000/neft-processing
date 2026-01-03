import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "owner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const mockProducts = {
  items: [
    {
      id: "product-1",
      partner_id: "partner-1",
      type: "SERVICE",
      title: "Диагностика",
      category: "Авто",
      price_model: "FIXED",
      price_config: { amount: 1500, currency: "RUB" },
      status: "DRAFT",
      updated_at: new Date().toISOString(),
      published_at: null,
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
};

const mockFetch = (url: string, init?: RequestInit) => {
  if (url.includes("/partner/products") && init?.method === "POST" && url.endsWith("/publish")) {
    return new Response(
      JSON.stringify({
        ...mockProducts.items[0],
        status: "PUBLISHED",
        published_at: new Date().toISOString(),
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/products") && init?.method === "POST") {
    return new Response(JSON.stringify(mockProducts.items[0]), { status: 201 });
  }
  if (url.includes("/partner/products") && !url.includes("/partner/products/")) {
    return new Response(JSON.stringify(mockProducts), { status: 200 });
  }
  if (url.includes("/partner/products/")) {
    return new Response(JSON.stringify({ ...mockProducts.items[0], description: "Полная диагностика" }), { status: 200 });
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200 });
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo, init?: RequestInit) => Promise.resolve(mockFetch(String(input), init))) as unknown as typeof fetch,
  );
  vi.spyOn(window, "confirm").mockImplementation(() => true);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("MarketplaceProductsPage", () => {
  it("renders products list", async () => {
    render(
      <MemoryRouter initialEntries={["/marketplace/products"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Диагностика")).toBeInTheDocument();
  });

  it("shows validation errors for price config", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/marketplace/products"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    await screen.findByText("Диагностика");

    await user.type(screen.getByLabelText("Название"), "Тест");
    await user.type(screen.getByLabelText("Категория"), "Сервис");
    await user.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    expect(await screen.findByText("Проверьте подсвеченные поля")).toBeInTheDocument();
  });

  it("publishes product", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/marketplace/products"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    await screen.findByText("Диагностика");
    await user.click(screen.getByRole("button", { name: "Опубликовать" }));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
    });
  });
});

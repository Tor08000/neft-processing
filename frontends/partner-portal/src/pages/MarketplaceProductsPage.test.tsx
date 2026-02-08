import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";
import type { MarketplaceProduct } from "../types/marketplace";

const session: AuthSession = {
  token: "token-1",
  email: "owner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const buildProduct = (overrides: Partial<MarketplaceProduct> = {}): MarketplaceProduct => ({
  id: "product-1",
  partner_id: "partner-1",
  title: "Диагностика",
  description: "Полная диагностика",
  category: "Авто",
  status: "DRAFT",
  updated_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
  tags: [],
  attributes: {},
  variants: [],
  media: [],
  ...overrides,
});

const mockFetchFactory = () => {
  const items: MarketplaceProduct[] = [buildProduct()];

  return (url: string, init?: RequestInit) => {
    if (url.includes("/partner/products") && init?.method === "POST" && url.endsWith("/submit")) {
      const updated = { ...items[0], status: "PENDING_REVIEW" as const };
      items[0] = updated;
      return new Response(JSON.stringify(updated), { status: 200 });
    }
    if (url.includes("/partner/products") && init?.method === "POST" && url.endsWith("/archive")) {
      const updated = { ...items[0], status: "ARCHIVED" as const };
      items[0] = updated;
      return new Response(JSON.stringify(updated), { status: 200 });
    }
    if (url.includes("/partner/products") && init?.method === "POST") {
      const payload = init?.body ? (JSON.parse(init.body as string) as Partial<MarketplaceProduct>) : {};
      const created = buildProduct({
        id: `product-${items.length + 1}`,
        title: payload.title ?? "Новый товар",
        description: payload.description ?? "",
        category: payload.category ?? "Категория",
      });
      items.push(created);
      return new Response(JSON.stringify(created), { status: 201 });
    }
    if (url.includes("/partner/products") && init?.method === "PATCH") {
      const payload = init?.body ? (JSON.parse(init.body as string) as Partial<MarketplaceProduct>) : {};
      items[0] = { ...items[0], ...payload };
      return new Response(JSON.stringify(items[0]), { status: 200 });
    }
    if (url.includes("/partner/products") && !url.includes("/partner/products/")) {
      return new Response(
        JSON.stringify({ items, total: items.length, limit: 50, offset: 0 }),
        { status: 200 },
      );
    }
    if (url.includes("/partner/products/")) {
      const product = items[0];
      return new Response(JSON.stringify(product), { status: 200 });
    }
    return new Response(JSON.stringify({ items: [] }), { status: 200 });
  };
};

beforeEach(() => {
  const mockFetch = mockFetchFactory();
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

  it("shows validation errors for required fields", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/marketplace/products"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    await screen.findByText("Диагностика");

    await user.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    expect(await screen.findByText("Проверьте подсвеченные поля")).toBeInTheDocument();
  });

  it("creates product and submits for review", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/marketplace/products"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    await screen.findByText("Диагностика");

    await user.type(screen.getByLabelText("Название"), "Новый товар");
    const categoryInputs = screen.getAllByLabelText("Категория");
    await user.type(categoryInputs[categoryInputs.length - 1], "Сервис");
    await user.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    expect(await screen.findByText("Новый товар")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Отправить на модерацию" }));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
    });
  });
});

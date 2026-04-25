import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import type { AuthSession } from "../api/types";
import i18n from "../i18n";
import { MarketplaceProductsPage } from "./MarketplaceProductsPage";
import type { MarketplaceProduct } from "../types/marketplace";

const session: AuthSession = {
  token: "token-1",
  email: "owner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

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
      const targetId = url.split("/").slice(-2)[0] ?? items[0].id;
      const index = items.findIndex((item) => item.id === targetId);
      const updated = { ...(items[index] ?? items[0]), status: "PENDING_REVIEW" as const };
      if (index >= 0) {
        items[index] = updated;
      } else {
        items[0] = updated;
      }
      return jsonResponse(updated);
    }
    if (url.includes("/partner/products") && init?.method === "POST" && url.endsWith("/archive")) {
      const targetId = url.split("/").slice(-2)[0] ?? items[0].id;
      const index = items.findIndex((item) => item.id === targetId);
      const updated = { ...(items[index] ?? items[0]), status: "ARCHIVED" as const };
      if (index >= 0) {
        items[index] = updated;
      } else {
        items[0] = updated;
      }
      return jsonResponse(updated);
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
      return jsonResponse(created, 201);
    }
    if (url.includes("/partner/products") && init?.method === "PATCH") {
      const targetId = url.split("/").pop() ?? items[0].id;
      const index = items.findIndex((item) => item.id === targetId);
      const payload = init?.body ? (JSON.parse(init.body as string) as Partial<MarketplaceProduct>) : {};
      const updated = { ...(items[index] ?? items[0]), ...payload };
      if (index >= 0) {
        items[index] = updated;
      } else {
        items[0] = updated;
      }
      return jsonResponse(updated);
    }
    if (url.includes("/partner/products") && !url.includes("/partner/products/")) {
      return jsonResponse({ items, total: items.length, limit: 50, offset: 0 });
    }
    if (url.includes("/partner/products/")) {
      const targetId = url.split("/").pop() ?? items[0].id;
      const product = items.find((item) => item.id === targetId) ?? items[0];
      return jsonResponse(product);
    }
    return jsonResponse({ items: [] });
  };
};

const renderPage = () =>
  render(
    <I18nextProvider i18n={i18n}>
      <AuthProvider initialSession={session}>
        <MemoryRouter initialEntries={["/marketplace/products"]}>
          <MarketplaceProductsPage />
        </MemoryRouter>
      </AuthProvider>
    </I18nextProvider>,
  );

const getCreateFormSection = () => {
  const heading = screen.getByRole("heading", { name: "Создание позиции" });
  const section = heading.closest("section");
  if (!section) {
    throw new Error("Create form section not found");
  }
  return section;
};

const getPrimaryFormGrid = (section: HTMLElement) => {
  const formGrid = section.querySelector(".form-grid");
  if (!formGrid) {
    throw new Error("Primary product form grid not found");
  }
  return formGrid as HTMLElement;
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
    renderPage();

    expect(await screen.findByRole("heading", { name: "Каталог маркетплейса" })).toBeInTheDocument();
    expect(screen.getByText("Диагностика")).toBeInTheDocument();
  });

  it("keeps draft save disabled for empty required fields", async () => {
    renderPage();

    await screen.findByRole("heading", { name: "Каталог маркетплейса" });

    const saveDraftButton = screen.getByRole("button", { name: "Сохранить черновик" });
    expect(saveDraftButton).toBeDisabled();
  });

  it("creates product and submits for review", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole("heading", { name: "Каталог маркетплейса" });

    const createSection = getCreateFormSection();
    const primaryFormGrid = getPrimaryFormGrid(createSection);
    await user.type(within(primaryFormGrid).getByLabelText("Название"), "Новый товар");
    await user.type(within(primaryFormGrid).getByLabelText("Категория"), "Сервис");
    await user.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    const createdTitle = await screen.findByText("Новый товар");
    const createdRow = createdTitle.closest("tr");
    expect(createdRow).not.toBeNull();

    await user.click(within(createdRow as HTMLTableRowElement).getByRole("button", { name: "Отправить на модерацию" }));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
    });

    await waitFor(() => {
      const submittedTitle = screen.getByText("Новый товар");
      const submittedRow = submittedTitle.closest("tr");
      expect(submittedRow).not.toBeNull();
      expect(within(submittedRow as HTMLTableRowElement).getByText("На модерации")).toBeInTheDocument();
    });
  });
});

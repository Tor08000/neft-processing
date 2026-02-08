import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";
import type { MarketplaceOffer } from "../types/marketplace";

const session: AuthSession = {
  token: "token-1",
  email: "owner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const buildOffer = (overrides: Partial<MarketplaceOffer> = {}): MarketplaceOffer => ({
  id: "offer-1",
  partner_id: "partner-1",
  subject_type: "PRODUCT",
  subject_id: "product-1",
  title_override: "Пакет мойки",
  description_override: null,
  status: "DRAFT",
  moderation_comment: null,
  currency: "RUB",
  price_model: "FIXED",
  price_amount: 1000,
  price_min: null,
  price_max: null,
  vat_rate: null,
  terms: {},
  geo_scope: "ALL_PARTNER_LOCATIONS",
  location_ids: [],
  region_code: null,
  entitlement_scope: "ALL_CLIENTS",
  allowed_subscription_codes: [],
  allowed_client_ids: [],
  valid_from: null,
  valid_to: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

const mockFetchFactory = () => {
  const items: MarketplaceOffer[] = [buildOffer()];

  return (url: string, init?: RequestInit) => {
    if (url.includes("/marketplace/partner/offers") && init?.method === "POST" && url.endsWith(":submit")) {
      items[0] = { ...items[0], status: "PENDING_REVIEW" };
      return new Response(JSON.stringify(items[0]), { status: 200 });
    }
    if (url.includes("/marketplace/partner/offers") && init?.method === "POST") {
      const payload = init?.body ? (JSON.parse(init.body as string) as Partial<MarketplaceOffer>) : {};
      const created = buildOffer({
        id: `offer-${items.length + 1}`,
        subject_id: payload.subject_id ?? "product-new",
        title_override: payload.title_override ?? "Новый оффер",
        price_amount: payload.price_amount ?? 1200,
      });
      items.push(created);
      return new Response(JSON.stringify(created), { status: 201 });
    }
    if (url.includes("/marketplace/partner/offers/") && !url.includes(":submit") && init?.method === "PATCH") {
      const payload = init?.body ? (JSON.parse(init.body as string) as Partial<MarketplaceOffer>) : {};
      items[0] = { ...items[0], ...payload } as MarketplaceOffer;
      return new Response(JSON.stringify(items[0]), { status: 200 });
    }
    if (url.includes("/marketplace/partner/offers/") && !url.endsWith(":submit")) {
      const offerId = url.split("/").pop() ?? "offer-1";
      const offer = items.find((item) => item.id === offerId) ?? items[0];
      return new Response(JSON.stringify(offer), { status: 200 });
    }
    if (url.includes("/marketplace/partner/offers")) {
      return new Response(JSON.stringify({ items, total: items.length, limit: 50, offset: 0 }), { status: 200 });
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

describe("MarketplaceOffersPage", () => {
  it("renders offers list", async () => {
    render(
      <MemoryRouter initialEntries={["/marketplace/offers"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Пакет мойки")).toBeInTheDocument();
  });

  it("creates a draft offer", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/marketplace/offers"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    await screen.findByText("Пакет мойки");

    await user.type(screen.getByLabelText("ID предмета"), "product-new");
    await user.type(screen.getByLabelText("Цена"), "1500");
    await user.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    expect(await screen.findByText("Новый оффер")).toBeInTheDocument();
  });

  it("submits offer for review", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/marketplace/offers"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    await screen.findByText("Пакет мойки");

    await user.click(screen.getByRole("button", { name: "Отправить на модерацию" }));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
    });

    expect(await screen.findByText("На модерации")).toBeInTheDocument();
  });
});

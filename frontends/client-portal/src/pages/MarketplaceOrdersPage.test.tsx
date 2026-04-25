import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "../api/types";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import { MarketplaceOrdersPage } from "./MarketplaceOrdersPage";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_ADMIN"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const buildOrdersResponse = () =>
  new Response(
    JSON.stringify({
      items: [
        {
          id: "order-1",
          status: "CREATED",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          total_amount: 1000,
          currency: "RUB",
        },
        {
          id: "order-2",
          status: "PENDING_PAYMENT",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          total_amount: 1500,
          currency: "RUB",
        },
        {
          id: "order-3",
          status: "CONFIRMED_BY_PARTNER",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          total_amount: 2000,
          currency: "RUB",
        },
      ],
      total: 3,
    }),
    { status: 200 },
  );

const mockFetch = (url: string) => {
  if (url.includes("/v1/marketplace/client/orders")) {
    return buildOrdersResponse();
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200 });
};

describe("MarketplaceOrdersPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders backend-owned statuses and exposes cancel for created and pending-payment orders", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/orders"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={session}>
            <MarketplaceOrdersPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    const createdRow = (await screen.findByText("order-1")).closest("tr");
    const pendingPaymentRow = screen.getByText("order-2").closest("tr");
    const confirmedRow = screen.getByText("order-3").closest("tr");

    expect(createdRow).not.toBeNull();
    expect(pendingPaymentRow).not.toBeNull();
    expect(confirmedRow).not.toBeNull();

    expect(within(createdRow as HTMLElement).getByText("Создан")).toBeInTheDocument();
    expect(within(pendingPaymentRow as HTMLElement).getByText("Ожидает оплаты")).toBeInTheDocument();
    expect(within(confirmedRow as HTMLElement).getByText("Подтверждён партнёром")).toBeInTheDocument();

    expect(within(createdRow as HTMLElement).getByRole("button", { name: "Отменить" })).toBeInTheDocument();
    expect(within(pendingPaymentRow as HTMLElement).getByRole("button", { name: "Отменить" })).toBeInTheDocument();
    expect(within(confirmedRow as HTMLElement).queryByRole("button", { name: "Отменить" })).toBeNull();

    expect(screen.queryByRole("option", { name: "Принят" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Отменён" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сбросить фильтры" })).toBeDisabled();
    expect(screen.getByText("Rows: 3")).toBeInTheDocument();
  });

  it("sends backend-compatible cancel body from the live page flow", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      if (url.includes("/v1/marketplace/client/orders/order-1/cancel")) {
        return Promise.resolve(new Response(JSON.stringify({ id: "order-1", status: "CANCELED_BY_CLIENT" }), { status: 200 }));
      }
      return Promise.resolve(mockFetch(url));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    vi.stubGlobal("confirm", vi.fn(() => true));

    render(
      <MemoryRouter initialEntries={["/marketplace/orders"]}>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={session}>
            <MarketplaceOrdersPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    const createdRow = (await screen.findByText("order-1")).closest("tr");
    expect(createdRow).not.toBeNull();

    const cancelButton = within(createdRow as HTMLElement).getByRole("button", { name: "Отменить" });
    await userEvent.click(cancelButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/v1/marketplace/client/orders/order-1/cancel"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ reason: null }),
        }),
      );
    });
  });
});

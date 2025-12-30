import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const ownerSession: AuthSession = {
  token: "token-1",
  email: "owner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const operatorSession: AuthSession = {
  ...ownerSession,
  email: "operator@demo.test",
  roles: ["PARTNER_OPERATOR"],
};

const accountantSession: AuthSession = {
  ...ownerSession,
  email: "accountant@demo.test",
  roles: ["PARTNER_ACCOUNTANT"],
};

const orderPayload = {
  id: "order-1",
  clientId: "client-1",
  clientName: "Иван",
  partnerId: "partner-1",
  items: [{ offerId: "offer-1", title: "Мойка", qty: 1, unitPrice: 1000, amount: 1000 }],
  status: "PAID",
  paymentStatus: "PAID",
  totalAmount: 1000,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

const mockFetch = (url: string) => {
  if (url.includes("/partner/orders/order-1/events")) {
    return new Response(
      JSON.stringify([
        {
          id: "event-1",
          type: "CREATED",
          createdAt: new Date().toISOString(),
        },
      ]),
      { status: 200 },
    );
  }
  if (url.includes("/partner/orders/order-1/documents")) {
    return new Response(
      JSON.stringify([
        {
          id: "doc-1",
          type: "Invoice",
          status: "SIGNED",
          signatureStatus: "SIGNED",
          edoStatus: "OK",
          url: "https://example.com/doc.pdf",
        },
      ]),
      { status: 200 },
    );
  }
  if (url.includes("/partner/refunds")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "refund-1",
            orderId: "order-1",
            status: "OPEN",
            amount: 200,
            createdAt: new Date().toISOString(),
          },
        ],
        page: 1,
        pageSize: 20,
        total: 1,
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/settlements")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "set-1",
            status: "sent",
            periodStart: new Date().toISOString(),
            periodEnd: new Date().toISOString(),
            payoutBatchId: "batch-1",
          },
        ],
        page: 1,
        pageSize: 10,
        total: 1,
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/orders/order-1")) {
    return new Response(JSON.stringify(orderPayload), { status: 200 });
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

describe("OrderDetailsPage", () => {
  it("renders order details", async () => {
    render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Заказ order-1/)).toBeInTheDocument();
    expect(await screen.findByText(/Позиции/)).toBeInTheDocument();
    expect(screen.getByText("Мойка")).toBeInTheDocument();
  });

  it("gates lifecycle actions by role", async () => {
    const { unmount } = render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "Подтвердить" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отменить" })).toBeInTheDocument();

    unmount();
    const operatorRender = render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <App initialSession={operatorSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "Подтвердить" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отменить" })).not.toBeInTheDocument();

    operatorRender.unmount();
    render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <App initialSession={accountantSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Действия недоступны/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Подтвердить" })).not.toBeInTheDocument();
  });

  it("requires reason to cancel", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    const cancelButton = await screen.findByRole("button", { name: "Отменить" });
    await user.click(cancelButton);

    const dialog = await screen.findByRole("dialog");
    const confirmButton = within(dialog).getByRole("button", { name: "Подтвердить" });
    expect(confirmButton).toBeDisabled();

    const reasonInput = within(dialog).getByPlaceholderText(/Опишите причину отмены/);
    await user.type(reasonInput, "Нет возможности выполнить");
    expect(confirmButton).not.toBeDisabled();
  });
});

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

const buildMockFetch = (orderPayload: Record<string, unknown>) => (url: string) => {
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
  if (url.includes("/partner/orders/order-1/sla")) {
    return new Response(
      JSON.stringify({
        obligations: [
          {
            metric: "response_time",
            remainingSeconds: 600,
            totalSeconds: 3600,
            status: "OK",
          },
        ],
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
            status: "SENT",
            periodStart: new Date().toISOString(),
            periodEnd: new Date().toISOString(),
            net_amount: 850,
          },
        ],
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
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo) => Promise.resolve(buildMockFetch(orderPayloadCreated)(String(input)))) as unknown as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const orderPayloadCreated = {
  id: "order-1",
  clientId: "client-1",
  clientName: "Иван",
  partnerId: "partner-1",
  items: [{ offerId: "offer-1", title: "Мойка", qty: 1, unitPrice: 1000, amount: 1000 }],
  status: "CREATED",
  paymentStatus: "PAID",
  totalAmount: 1000,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

const orderPayloadProgress = {
  ...orderPayloadCreated,
  status: "IN_PROGRESS",
};

describe("OrderDetailsPage", () => {
  it("shows accept and reject on CREATED", async () => {
    render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Заказ order-1/)).toBeInTheDocument();
    const acceptButton = screen.getByRole("button", { name: "Принять" });
    const rejectButton = screen.getByRole("button", { name: "Отклонить" });
    expect(acceptButton).toBeEnabled();
    expect(rejectButton).toBeEnabled();
  });

  it("validates progress modal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => Promise.resolve(buildMockFetch(orderPayloadProgress)(String(input)))) as unknown as typeof fetch,
    );
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    const progressButton = await screen.findByRole("button", { name: "Обновить прогресс" });
    await user.click(progressButton);

    const dialog = await screen.findByRole("dialog");
    const confirmButton = within(dialog).getByRole("button", { name: "Подтвердить" });
    expect(confirmButton).toBeDisabled();

    const percentInput = within(dialog).getByLabelText("Прогресс, %") as HTMLInputElement;
    await user.type(percentInput, "50");
    expect(confirmButton).not.toBeDisabled();
  });
});

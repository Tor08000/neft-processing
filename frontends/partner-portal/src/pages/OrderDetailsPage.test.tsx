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
  if (url.includes("/v1/marketplace/partner/orders/order-1/events")) {
    return new Response(
      JSON.stringify([
        {
          id: "event-1",
          event_type: "CREATED",
          created_at: new Date().toISOString(),
        },
      ]),
      { status: 200 },
    );
  }
  if (url.includes("/v1/marketplace/partner/orders/order-1/sla")) {
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
  if (url.includes("/v1/marketplace/partner/orders/order-1")) {
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
  client_id: "client-1",
  partner_id: "partner-1",
  status: "PAID",
  payment_status: "PAID",
  total_amount: 1000,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  lines: [{ offer_id: "offer-1", title_snapshot: "Мойка", qty: 1, unit_price: 1000, line_amount: 1000 }],
};

describe("OrderDetailsPage", () => {
  it("shows confirm and decline on PAID", async () => {
    render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Заказ order-1/)).toBeInTheDocument();
    const confirmButton = screen.getByRole("button", { name: "Подтвердить" });
    const declineButton = screen.getByRole("button", { name: "Отклонить" });
    expect(confirmButton).toBeEnabled();
    expect(declineButton).toBeEnabled();
  });

  it("validates decline modal", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    const declineButton = await screen.findByRole("button", { name: "Отклонить" });
    await user.click(declineButton);

    const dialog = await screen.findByRole("dialog");
    const confirmButton = within(dialog).getByRole("button", { name: "Подтвердить" });
    expect(confirmButton).toBeDisabled();

    const reasonInput = within(dialog).getByLabelText("Причина отказа") as HTMLInputElement;
    const commentInput = within(dialog).getByLabelText("Комментарий") as HTMLInputElement;
    await user.type(reasonInput, "OUT_OF_STOCK");
    await user.type(commentInput, "Нет на складе");
    expect(confirmButton).not.toBeDisabled();
  });
});

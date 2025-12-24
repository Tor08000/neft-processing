import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_USER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("Client invoices", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders empty state when no invoices", async () => {
    const invoicesResponse = new Response(
      JSON.stringify({
        items: [],
        total: 0,
        limit: 25,
        offset: 0,
      }),
      { status: 200 },
    );

    const fetchMock = vi.fn().mockResolvedValueOnce(invoicesResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/finance/invoices"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Инвойсы/)).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/Счета не найдены/)).toBeInTheDocument();
  });

  it("opens invoice details", async () => {
    const detailResponse = new Response(
      JSON.stringify({
        id: "inv-2",
        number: "INV-2024-02",
        issued_at: "2024-03-05T00:00:00Z",
        currency: "RUB",
        amount_total: 1500,
        amount_paid: 1000,
        amount_refunded: 0,
        amount_due: 500,
        status: "PAID",
        pdf_available: true,
        payments: [
          {
            id: "pay-1",
            amount: 1000,
            status: "POSTED",
            provider: "bank",
            external_ref: "ext-1",
            created_at: "2024-03-06T10:00:00Z",
          },
        ],
        refunds: [],
      }),
      { status: 200 },
    );

    const fetchMock = vi.fn().mockResolvedValue(detailResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/finance/invoices/inv-2"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/INV-2024-02/)).toBeInTheDocument();
    expect(screen.getByText(/Платежи/)).toBeInTheDocument();
    expect(screen.getByText(/1500/)).toBeInTheDocument();
  });
});

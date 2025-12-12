import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("renders list with filters", async () => {
    const invoicesResponse = new Response(
      JSON.stringify({
        items: [
          {
            id: "inv-1",
            period_from: "2024-01-01",
            period_to: "2024-01-31",
            currency: "RUB",
            total_amount: 1000,
            tax_amount: 0,
            total_with_tax: 1000,
            status: "ISSUED",
            issued_at: "2024-02-01",
          },
        ],
        total: 1,
        limit: 1,
        offset: 0,
      }),
      { status: 200 },
    );

    const filteredResponse = new Response(
      JSON.stringify({ items: [], total: 0, limit: 0, offset: 0 }),
      { status: 200 },
    );

    const fetchMock = vi.fn().mockResolvedValueOnce(invoicesResponse).mockResolvedValueOnce(filteredResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/invoices"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Счета/)).toBeInTheDocument();
    expect(screen.getByText(/1000/)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/Статус/i), "PAID");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const lastCall = fetchMock.mock.calls[1]?.[0] as string;
    expect(lastCall).toContain("status=PAID");
  });

  it("opens invoice details", async () => {
    const detailResponse = new Response(
      JSON.stringify({
        id: "inv-2",
        period_from: "2024-02-01",
        period_to: "2024-02-29",
        currency: "RUB",
        total_amount: 1500,
        tax_amount: 200,
        total_with_tax: 1700,
        status: "PAID",
        issued_at: "2024-03-05",
        paid_at: "2024-03-10",
        lines: [
          { card_id: "card-1", product_id: "diesel", liters: 50, amount: 1500, tax_amount: 200 },
        ],
      }),
      { status: 200 },
    );

    const fetchMock = vi.fn().mockResolvedValue(detailResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/invoices/inv-2"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Счет inv-2/)).toBeInTheDocument();
    expect(screen.getByText(/diesel/)).toBeInTheDocument();
    expect(screen.getByText(/1700/)).toBeInTheDocument();
  });
});

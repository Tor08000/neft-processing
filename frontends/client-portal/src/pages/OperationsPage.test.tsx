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

describe("Client operations", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders list with filters and pagination", async () => {
    const cardsResponse = new Response(
      JSON.stringify({ items: [{ id: "card-1", pan_masked: "1111", status: "ACTIVE", limits: [] }] }),
      { status: 200 },
    );
    const operationsResponse = new Response(
      JSON.stringify({
        items: [
          {
            id: "op-1",
            created_at: "2024-01-01T10:00:00Z",
            amount: 1000,
            currency: "RUB",
            status: "APPROVED",
            card_id: "card-1",
            merchant_id: "azs-7",
            product_type: "DIESEL",
            quantity: 20,
          },
        ],
        total: 1,
        limit: 10,
        offset: 0,
      }),
      { status: 200 },
    );
    const filteredResponse = new Response(
      JSON.stringify({
        items: [],
        total: 0,
        limit: 10,
        offset: 0,
      }),
      { status: 200 },
    );

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(cardsResponse)
      .mockResolvedValueOnce(operationsResponse)
      .mockResolvedValueOnce(filteredResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/operations"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Операции/)).toBeInTheDocument();
    expect(await screen.findByText(/azs-7/)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/Статус/i), "DECLINED");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const lastCall = fetchMock.mock.calls[2]?.[0] as string;
    expect(lastCall).toContain("status=DECLINED");
  });

  it("opens operation details", async () => {
    const detailResponse = new Response(
      JSON.stringify({
        id: "op-2",
        created_at: "2024-01-02T12:00:00Z",
        amount: 1500,
        currency: "RUB",
        status: "DECLINED",
        card_id: "card-9",
        merchant_id: "azs-9",
        product_type: "AI95",
        quantity: 30,
        reason: "Превышен дневной лимит договора",
      }),
      { status: 200 },
    );

    const fetchMock = vi.fn().mockResolvedValue(detailResponse);
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/operations/op-2"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Превышен дневной лимит договора/)).toBeInTheDocument();
    expect(screen.getByText(/op-2/)).toBeInTheDocument();
  });
});

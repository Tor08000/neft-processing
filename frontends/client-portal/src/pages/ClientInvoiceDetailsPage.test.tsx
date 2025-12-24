import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
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

describe("Client invoice details timeline", () => {
  it("renders empty state for timeline", async () => {
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
        payments: [],
        refunds: [],
      }),
      { status: 200 },
    );

    const auditResponse = new Response(
      JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }),
      { status: 200 },
    );

    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/invoices/inv-2/audit")) {
        return auditResponse;
      }
      return detailResponse;
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/finance/invoices/inv-2"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/INV-2024-02/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /История/i }));

    expect(await screen.findByText(/История пока пуста/)).toBeInTheDocument();
  });
});

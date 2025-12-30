import { render, screen } from "@testing-library/react";
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

const accountantSession: AuthSession = {
  ...ownerSession,
  email: "accountant@demo.test",
  roles: ["PARTNER_ACCOUNTANT"],
};

const refundPayload = {
  id: "refund-1",
  orderId: "order-1",
  status: "OPEN",
  amount: 200,
  reason: "Повреждение",
  createdAt: new Date().toISOString(),
};

const mockFetch = (url: string) => {
  if (url.includes("/partner/refunds/refund-1")) {
    return new Response(JSON.stringify(refundPayload), { status: 200 });
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

describe("RefundDetailsPage", () => {
  it("shows approve/deny buttons for owner", async () => {
    render(
      <MemoryRouter initialEntries={["/refunds/refund-1"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "Одобрить" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отклонить" })).toBeInTheDocument();
  });

  it("hides approve/deny buttons for accountant", async () => {
    render(
      <MemoryRouter initialEntries={["/refunds/refund-1"]}>
        <App initialSession={accountantSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Действия недоступны/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Одобрить" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отклонить" })).not.toBeInTheDocument();
  });
});

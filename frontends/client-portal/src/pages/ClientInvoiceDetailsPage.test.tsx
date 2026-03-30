import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ClientInvoiceDetailsPage } from "./ClientInvoiceDetailsPage";
import { AuthProvider } from "../auth/AuthContext";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const invoicePayload = {
  id: 101,
  org_id: 1,
  period_start: "2025-02-01",
  period_end: "2025-02-28",
  status: "ISSUED",
  amount_total: 1000,
  amount_paid: 0,
  amount_refunded: 0,
  amount_due: 1000,
  currency: "RUB",
  due_at: "2025-03-10",
  download_url: "/api/client/invoices/101/download",
  payments: [],
  refunds: [],
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify(invoicePayload), { status: 200 }))) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ClientInvoiceDetailsPage", () => {
  it("renders invoice summary", async () => {
    render(
      <MemoryRouter initialEntries={["/invoices/101"]}>
        <AuthProvider initialSession={session}>
          <Routes>
            <Route path="/invoices/:id" element={<ClientInvoiceDetailsPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Счёт #101")).toBeInTheDocument();
    expect(screen.getByText(/Скачать PDF/)).toBeInTheDocument();
  });
});

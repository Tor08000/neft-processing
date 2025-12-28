import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  id: "inv-1",
  number: "INV-001",
  issued_at: "2025-02-01T10:00:00Z",
  status: "SENT",
  amount_total: 1000,
  amount_paid: 0,
  amount_refunded: 0,
  amount_due: 1000,
  currency: "RUB",
  pdf_available: true,
  acknowledged: false,
  ack_at: null,
  payments: [],
  refunds: [],
};

const emptyMessages = { items: [], total: 0, limit: 50, offset: 0 };
const auditPayload = {
  items: [
    {
      id: "audit-1",
      ts: "2025-02-02T10:00:00Z",
      event_type: "INVOICE_CREATED",
      entity_type: "invoice",
      entity_id: "inv-1",
      action: "CREATE",
      visibility: "PUBLIC",
    },
    {
      id: "audit-2",
      ts: "2025-02-02T11:00:00Z",
      event_type: "ADMIN_MANUAL_FIX",
      entity_type: "invoice",
      entity_id: "inv-1",
      action: "UPDATE",
      visibility: "INTERNAL",
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/invoices/inv-1/messages") && (!init || init.method === "GET")) {
      return Promise.resolve(new Response(JSON.stringify(emptyMessages), { status: 200 }));
    }
    if (url.includes("/invoices/inv-1/audit")) {
      return Promise.resolve(new Response(JSON.stringify(auditPayload), { status: 200 }));
    }
    if (url.includes("/invoices/inv-1") && (!init || init.method === "GET")) {
      return Promise.resolve(new Response(JSON.stringify(invoicePayload), { status: 200 }));
    }
    if (url.includes("/documents/INVOICE_PDF/inv-1/ack")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({ acknowledged: true, ack_at: "2025-02-02T10:00:00Z", document_type: "INVOICE_PDF" }),
          { status: 201 },
        ),
      );
    }
    if (url.includes("/invoices/inv-1/messages") && init?.method === "POST") {
      return Promise.resolve(
        new Response(JSON.stringify({ thread_id: "thread-1", message_id: "msg-1", status: "OPEN" }), {
          status: 201,
        }),
      );
    }
    return Promise.resolve(new Response("Not Found", { status: 404 }));
  }) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ClientInvoiceDetailsPage", () => {
  it("updates acknowledgement state", async () => {
    render(
      <AuthProvider initialSession={session}>
        <MemoryRouter initialEntries={["/finance/invoices/inv-1"]}>
          <Routes>
            <Route path="/finance/invoices/:id" element={<ClientInvoiceDetailsPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(await screen.findByText("INV-001")).toBeInTheDocument();

    const ackButton = await screen.findByRole("button", { name: "Подтвердить получение" });
    await userEvent.click(ackButton);

    await waitFor(() => {
      expect(screen.getByText(/Получено/)).toBeInTheDocument();
    });
  });

  it("adds new message to the list", async () => {
    render(
      <AuthProvider initialSession={session}>
        <MemoryRouter initialEntries={["/finance/invoices/inv-1"]}>
          <Routes>
            <Route path="/finance/invoices/:id" element={<ClientInvoiceDetailsPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(await screen.findByText("INV-001")).toBeInTheDocument();

    const textarea = await screen.findByPlaceholderText("Напишите вопрос по счету");
    await userEvent.type(textarea, "Уточните назначение платежа");

    await userEvent.click(screen.getByRole("button", { name: "Отправить" }));

    await waitFor(() => {
      expect(screen.getByText("Уточните назначение платежа")).toBeInTheDocument();
    });
  });

  it("renders only public audit events in timeline", async () => {
    render(
      <AuthProvider initialSession={session}>
        <MemoryRouter initialEntries={["/finance/invoices/inv-1"]}>
          <Routes>
            <Route path="/finance/invoices/:id" element={<ClientInvoiceDetailsPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(await screen.findByText("INV-001")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "История" }));

    await waitFor(() => {
      expect(screen.getByText("Счет создан")).toBeInTheDocument();
    });
    expect(screen.queryByText("ADMIN_MANUAL_FIX")).not.toBeInTheDocument();
  });
});

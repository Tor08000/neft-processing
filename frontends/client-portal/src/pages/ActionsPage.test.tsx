import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { listClientDocuments, acknowledgeClientDocument, fetchExports, acknowledgeReconciliationRequest, createInvoiceMessage } =
  vi.hoisted(() => ({
    listClientDocuments: vi.fn(),
    acknowledgeClientDocument: vi.fn(),
    fetchExports: vi.fn(),
    acknowledgeReconciliationRequest: vi.fn(),
    createInvoiceMessage: vi.fn(),
  }));

const session = {
  token: "test.header.payload",
  email: "client@example.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 60_000,
};

vi.mock("../api/client/documents", async () => {
  const actual = await vi.importActual<typeof import("../api/client/documents")>("../api/client/documents");
  return {
    ...actual,
    listClientDocuments,
    acknowledgeClientDocument,
  };
});

vi.mock("../api/exports", () => ({
  fetchExports,
}));

vi.mock("../api/reconciliation", () => ({
  acknowledgeReconciliationRequest,
}));

vi.mock("../api/invoices", () => ({
  createInvoiceMessage,
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: session }),
}));

import { ActionsPage } from "./ActionsPage";

describe("ActionsPage", () => {
  beforeEach(() => {
    listClientDocuments
      .mockResolvedValueOnce({
        items: [
          {
            id: "doc-inbound",
            direction: "inbound",
            title: "Входящий акт",
            doc_type: "ACT",
            status: "RECEIVED",
            counterparty_name: null,
            number: "A-001",
            date: "2026-03-31",
            amount: "1200.00",
            currency: "RUB",
            created_at: "2026-03-31T12:00:00Z",
            files_count: 2,
            requires_action: false,
            action_code: null,
            ack_at: null,
            edo_status: "FAILED",
            period_from: "2026-03-01",
            period_to: "2026-03-31",
          },
          {
            id: "doc-safe",
            direction: "inbound",
            title: "Спокойный счет",
            doc_type: "INVOICE",
            status: "SIGNED",
            counterparty_name: null,
            number: "I-100",
            date: "2026-03-31",
            amount: "900.00",
            currency: "RUB",
            created_at: "2026-03-30T12:00:00Z",
            files_count: 1,
            requires_action: false,
            action_code: null,
            ack_at: "2026-04-01T10:00:00Z",
            edo_status: "DELIVERED",
            period_from: "2026-03-01",
            period_to: "2026-03-31",
          },
        ],
        total: 2,
        limit: 50,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: "doc-outbound",
            direction: "outbound",
            title: "Исходящий пакет",
            doc_type: "LETTER",
            status: "DRAFT",
            counterparty_name: null,
            number: null,
            date: null,
            amount: null,
            currency: null,
            created_at: "2026-04-02T09:00:00Z",
            files_count: 0,
            requires_action: true,
            action_code: "UPLOAD_OR_SUBMIT",
            ack_at: null,
            edo_status: null,
            period_from: null,
            period_to: null,
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      });
    fetchExports.mockResolvedValue({ items: [] });
    acknowledgeClientDocument.mockResolvedValue({
      acknowledged: true,
      ack_at: "2026-04-08T10:00:00Z",
      document_type: "ACT",
      document_object_key: "docs/doc-inbound.pdf",
      document_hash: "hash-1",
    });
    acknowledgeReconciliationRequest.mockResolvedValue(undefined);
    createInvoiceMessage.mockResolvedValue({ message_id: "msg-1" });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("uses canonical documents list for inbox discovery while keeping legacy document links", async () => {
    render(
      <MemoryRouter>
        <ActionsPage />
      </MemoryRouter>,
    );

    const openLinks = await screen.findAllByRole("link", { name: "Открыть" });
    expect(openLinks).toHaveLength(2);
    expect(openLinks[0]).toHaveAttribute("href", "/documents/doc-inbound");
    expect(openLinks[1]).toHaveAttribute("href", "/documents/doc-outbound");

    expect(screen.getByText("Ожидает")).toBeInTheDocument();
    expect(screen.getByText("Ошибка ЭДО")).toBeInTheDocument();
    expect(screen.getAllByText("Подготовить").length).toBeGreaterThan(0);
    expect(screen.getByText(/Исходящий пакет/)).toBeInTheDocument();
    expect(screen.getByText("Элементов inbox: 2")).toBeInTheDocument();
    expect(screen.queryByText("Спокойный счет")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Запросить подпись" })).toHaveAttribute(
      "href",
      "/client/support/new?topic=document_signature",
    );
    expect(screen.getByRole("link", { name: "Запросить ЭДО-отправку" })).toHaveAttribute(
      "href",
      "/client/support/new?topic=document_edo",
    );

    expect(listClientDocuments).toHaveBeenNthCalledWith(1, { direction: "inbound", limit: 50, offset: 0 }, session);
    expect(listClientDocuments).toHaveBeenNthCalledWith(2, { direction: "outbound", limit: 50, offset: 0 }, session);
  });

  it("submits manual document acknowledgement through the canonical helper", async () => {
    render(
      <MemoryRouter>
        <ActionsPage />
      </MemoryRouter>,
    );

    await screen.findByText(/Входящий акт/);

    fireEvent.change(screen.getByLabelText("ID документа"), { target: { value: "doc-inbound" } });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));

    await waitFor(() => {
      expect(acknowledgeClientDocument).toHaveBeenCalledWith("doc-inbound", session);
    });
    expect(await screen.findByText(/Документ подтвержден/)).toBeInTheDocument();
  });
});

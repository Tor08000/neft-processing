import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { listClientDocuments, createOutboundDocument } = vi.hoisted(() => ({
  listClientDocuments: vi.fn(),
  createOutboundDocument: vi.fn(),
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
    createOutboundDocument,
  };
});

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: session }),
}));

import { DocumentsPage } from "./DocumentsPage";

describe("DocumentsPage", () => {
  beforeEach(() => {
    listClientDocuments.mockResolvedValue({
      items: [
        {
          id: "doc-attention",
          direction: "inbound",
          title: "Акт за март",
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
          title: "Подписанный счет",
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
      total: 3,
      limit: 20,
      offset: 0,
    });
    createOutboundDocument.mockResolvedValue({ id: "created-1" });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders canonical period groups and derived attention state from canonical list fields", async () => {
    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Акт за март")).toBeInTheDocument();
    expect(screen.getByText("2026-03")).toBeInTheDocument();
    expect(screen.getByText("Без периода")).toBeInTheDocument();
    expect(screen.getAllByText("01.03.2026 — 31.03.2026")).toHaveLength(2);
    expect(screen.getByText("Акт")).toBeInTheDocument();
    expect(screen.getByText("Счет")).toBeInTheDocument();
    expect(screen.getAllByText("Требует внимания")).toHaveLength(2);
    expect(screen.getByText("Ошибка ЭДО")).toBeInTheDocument();
    expect(screen.getByText("Доставлен")).toBeInTheDocument();
    expect(screen.getByText("Ожидает")).toBeInTheDocument();
    expect(screen.getByText("Подписан")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Внимание"), { target: { value: "attention" } });

    expect(screen.getByText("Акт за март")).toBeInTheDocument();
    expect(screen.getByText("Исходящий пакет")).toBeInTheDocument();
    expect(screen.queryByText("Подписанный счет")).not.toBeInTheDocument();
    expect(screen.getByText("Требуют внимания на странице: 2")).toBeInTheDocument();

    const marchSection = screen.getByText("2026-03").closest("section");
    expect(marchSection).not.toBeNull();
    expect(within(marchSection as HTMLElement).getByText("Акт за март")).toBeInTheDocument();
  });
});

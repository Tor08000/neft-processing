import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BalancesPage } from "./BalancesPage";
import { ReconciliationRequestsPage } from "./ReconciliationRequestsPage";
import { ClientDocsListPage } from "./ClientDocsListPage";

const useAuthMock = vi.fn();
const fetchBalancesMock = vi.fn();
const fetchStatementsMock = vi.fn();
const fetchReconciliationRequestsMock = vi.fn();
const createReconciliationRequestMock = vi.fn();
const downloadReconciliationResultMock = vi.fn();
const fetchClientDocsListMock = vi.fn();
const downloadClientDocMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../api/balances", () => ({
  fetchBalances: (...args: unknown[]) => fetchBalancesMock(...args),
}));

vi.mock("../api/statements", () => ({
  fetchStatements: (...args: unknown[]) => fetchStatementsMock(...args),
}));

vi.mock("../api/reconciliation", () => ({
  fetchReconciliationRequests: (...args: unknown[]) => fetchReconciliationRequestsMock(...args),
  createReconciliationRequest: (...args: unknown[]) => createReconciliationRequestMock(...args),
  downloadReconciliationResult: (...args: unknown[]) => downloadReconciliationResultMock(...args),
}));

vi.mock("../api/clientDocs", () => ({
  fetchClientDocsList: (...args: unknown[]) => fetchClientDocsListMock(...args),
  downloadClientDoc: (...args: unknown[]) => downloadClientDocMock(...args),
}));

vi.mock("../components/CopyButton", () => ({
  CopyButton: () => <button type="button">Copy</button>,
}));

describe("Client read tables", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({
      user: {
        token: "test.header.payload",
        email: "finance@neft.test",
        roles: ["CLIENT_OWNER"],
      },
    });
  });

  it("renders balances inside the shared table shell", async () => {
    fetchBalancesMock.mockResolvedValue({
      items: [{ currency: "RUB", current: 1200, available: 900 }],
    });
    fetchStatementsMock.mockResolvedValue([
      { credits: 200, debits: 50 },
    ]);

    render(
      <MemoryRouter>
        <BalancesPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("RUB")).toBeInTheDocument();
    expect(screen.getByLabelText("Период с")).toBeInTheDocument();
    expect(screen.getByLabelText("Период по")).toBeInTheDocument();
    expect(screen.getByText("Счетов: 1")).toBeInTheDocument();
  });

  it("renders reconciliation history inside the shared table shell", async () => {
    fetchReconciliationRequestsMock.mockResolvedValue({
      items: [
        {
          id: "req-1",
          date_from: "2026-04-01",
          date_to: "2026-04-30",
          status: "GENERATED",
          note_client: "Monthly check",
          requested_at: "2026-04-12T10:00:00Z",
          result_hash_sha256: "abcdef0123456789",
          result_object_key: "files/recon-1.pdf",
        },
      ],
    });

    render(
      <MemoryRouter>
        <ReconciliationRequestsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Monthly check")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Обновить" })).toBeInTheDocument();
    expect(screen.getByText("Запросов: 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Скачать" })).toBeInTheDocument();
  });

  it("renders client documents with the shared table owner", async () => {
    fetchClientDocsListMock.mockResolvedValue({
      items: [
        {
          id: "doc-1",
          date: "2026-04-10",
          status: "READY",
          type: "INVOICE",
          download_url: "/files/doc-1.pdf",
        },
      ],
    });

    render(
      <MemoryRouter>
        <ClientDocsListPage title="Документы" docType="invoice" />
      </MemoryRouter>,
    );

    expect(await screen.findByText("INVOICE")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Скачать" })).toBeInTheDocument();
    expect(screen.getByText("Документов: 1")).toBeInTheDocument();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "../i18n";
import { ClientContractsPage } from "./ClientContractsPage";
import { ClientDocumentsPage } from "./ClientDocumentsPage";

const useAuthMock = vi.fn();
const fetchClientContractsMock = vi.fn();
const fetchDocumentsMock = vi.fn();
const downloadDocumentFileMock = vi.fn();
const acknowledgeClosingDocumentMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../api/portal", () => ({
  fetchClientContracts: (...args: unknown[]) => fetchClientContractsMock(...args),
}));

vi.mock("../api/documents", () => ({
  fetchDocuments: (...args: unknown[]) => fetchDocumentsMock(...args),
  downloadDocumentFile: (...args: unknown[]) => downloadDocumentFileMock(...args),
  acknowledgeClosingDocument: (...args: unknown[]) => acknowledgeClosingDocumentMock(...args),
}));

vi.mock("../pwa/mode", () => ({
  isPwaMode: false,
}));

vi.mock("@shared/demo/demo", () => ({
  isDemoClient: () => false,
}));

describe("Client read shell pages", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    useAuthMock.mockReturnValue({
      user: {
        token: "test.header.payload",
        email: "client@demo.test",
        roles: ["CLIENT_OWNER"],
      },
    });
  });

  it("renders contracts inside the shared table shell", async () => {
    fetchClientContractsMock.mockResolvedValue({
      items: [
        {
          contract_number: "CTR-001",
          contract_type: "FRAMEWORK",
          effective_from: "2026-01-01",
          effective_to: "2026-12-31",
          status: "ACTIVE",
          sla_status: "OK",
          sla_violations: 0,
        },
      ],
    });

    render(
      <MemoryRouter>
        <ClientContractsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("CTR-001")).toBeInTheDocument();
    expect(screen.getByText("Контрактов: 1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть" })).toHaveAttribute("href", "/contracts/CTR-001");
  });

  it("renders legacy documents through the shared table shell", async () => {
    fetchDocumentsMock.mockResolvedValue({
      items: [
        {
          id: "doc-1",
          document_type: "INVOICE",
          status: "ISSUED",
          period_from: "2026-03-01",
          period_to: "2026-03-31",
          version: 1,
          amount: 1200,
          number: "INV-001",
          created_at: "2026-04-01T12:00:00Z",
          updated_at: "2026-04-02T12:00:00Z",
          signature_status: "REQUESTED",
          edo_status: "SENT",
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    });

    render(
      <MemoryRouter>
        <I18nProvider locale="ru">
          <ClientDocumentsPage />
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("INV-001")).toBeInTheDocument();
    expect(screen.getByLabelText("Период с")).toBeInTheDocument();
    expect(screen.getByText("Показаны 1-1 из 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PDF" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть" })).toHaveAttribute("href", "/documents/doc-1");
    expect(screen.queryByRole("button", { name: "Отправить в ЭДО повторно" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Показать историю статусов" })).not.toBeInTheDocument();
  });

  it("keeps documents load failures inside the shared table error shell", async () => {
    fetchDocumentsMock.mockRejectedValue(new Error("gateway timeout"));

    render(
      <MemoryRouter>
        <I18nProvider locale="ru">
          <ClientDocumentsPage />
        </I18nProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Документы недоступны")).toBeInTheDocument();
    await waitFor(() => expect(fetchDocumentsMock).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
  });
});

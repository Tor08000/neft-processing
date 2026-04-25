import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/http";
import LegalPage from "./LegalPage";
import LegalPartnersPage from "./LegalPartnersPage";
import * as legalApi from "../../api/legal";
import * as legalPartnersApi from "../../api/legalPartners";

const useAuthMock = vi.fn();
const useAdminMock = vi.fn();

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../../admin/AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

vi.mock("../../api/legal", () => ({
  listLegalDocuments: vi.fn(),
  listLegalAcceptances: vi.fn(),
  createLegalDocument: vi.fn(),
  updateLegalDocument: vi.fn(),
  publishLegalDocument: vi.fn(),
}));

vi.mock("../../api/legalPartners", () => ({
  fetchLegalPartners: vi.fn(),
  fetchLegalPartner: vi.fn(),
  updateLegalPartnerStatus: vi.fn(),
}));

vi.mock("../../components/admin/AdminWriteActionModal", () => ({
  default: () => null,
}));

vi.mock("../../components/common/JsonViewer", () => ({
  JsonViewer: () => <div>json-viewer</div>,
}));

const Wrapper: React.FC<React.PropsWithChildren> = ({ children }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe("Legal owner routes", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "token-1" });
    useAdminMock.mockReturnValue({
      profile: {
        read_only: false,
        permissions: {
          legal: { read: true, operate: true, approve: true, write: true },
        },
      },
    });
    (legalApi.listLegalAcceptances as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    (legalPartnersApi.fetchLegalPartners as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
      cursor: null,
    });
  });

  it("distinguishes pristine and filtered-empty document states on the legal registry", async () => {
    (legalApi.listLegalDocuments as ReturnType<typeof vi.fn>).mockResolvedValue([]);

    render(
      <Wrapper>
        <MemoryRouter>
          <LegalPage />
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Legal registry is ready for the first document")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Code"), { target: { value: "LEGAL_TERMS" } });

    expect(await screen.findByText("No legal documents match the current filters")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset filters" })).toBeInTheDocument();
  });

  it("keeps partner detail honest with first-use detail state and structured retry error", async () => {
    (legalPartnersApi.fetchLegalPartners as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          partner_id: "partner-1",
          partner_name: "Partner One",
          legal_status: "PENDING_REVIEW",
          payout_blocked: false,
          updated_at: "2026-04-15T10:00:00Z",
        },
      ],
      total: 1,
      cursor: null,
    });
    (legalPartnersApi.fetchLegalPartner as ReturnType<typeof vi.fn>).mockRejectedValue(
      new ApiError(
        JSON.stringify({
          error: "internal_error",
          message: "Internal Server Error",
          request_id: "req-legal-partner-1",
        }),
        500,
        "req-legal-partner-1",
        "corr-legal-partner-1",
        "internal_error",
      ),
    );

    render(
      <Wrapper>
        <MemoryRouter>
          <LegalPartnersPage />
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Choose a partner to review legal detail")).toBeInTheDocument();

    fireEvent.click(await screen.findByText("partner-1"));

    expect(await screen.findByText("Failed to load partner detail")).toBeInTheDocument();
    expect(screen.getByText("Failed to load partner legal detail.")).toBeInTheDocument();
    expect(screen.getByText(/request_id: req-legal-partner-1/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();

    await waitFor(() => expect(legalPartnersApi.fetchLegalPartner).toHaveBeenCalled());
  });
});

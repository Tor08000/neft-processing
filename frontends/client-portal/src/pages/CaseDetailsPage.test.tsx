import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/http";
import { CaseDetailsPage } from "./CaseDetailsPage";

const useAuthMock = vi.fn();
const fetchCaseDetailsMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../api/cases", () => ({
  fetchCaseDetails: (...args: unknown[]) => fetchCaseDetailsMock(...args),
}));

const session = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const detailsPayload = {
  case: {
    id: "case-1",
    tenant_id: 1,
    kind: "support" as const,
    entity_type: "support_ticket",
    entity_id: "ticket-1",
    title: "Проблема с лимитами",
    description: "Подробности кейса",
    status: "TRIAGE" as const,
    queue: "SUPPORT" as const,
    priority: "MEDIUM" as const,
    escalation_level: 0,
    first_response_due_at: "2025-01-01T12:00:00Z",
    resolve_due_at: "2025-01-02T12:00:00Z",
    client_id: "client-1",
    partner_id: null,
    case_source_ref_type: "support_ticket",
    case_source_ref_id: "ticket-1",
    created_at: "2025-01-01T10:00:00Z",
    updated_at: "2025-01-01T10:10:00Z",
    last_activity_at: "2025-01-01T10:10:00Z",
  },
  comments: [],
  timeline: [],
  latest_snapshot: null,
  snapshots: [],
};

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/cases/case-1"]}>
      <Routes>
        <Route path="/cases/:id" element={<CaseDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("CaseDetailsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({ user: session });
    vi.stubGlobal("navigator", {
      clipboard: { writeText: vi.fn(() => Promise.resolve()) },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders explicit not-found state for a missing case", async () => {
    fetchCaseDetailsMock.mockRejectedValue(new ApiError("case_not_found", 404, "corr-case-404", null, "case_not_found"));

    renderPage();

    expect(await screen.findByText("Кейс не найден")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "К списку кейсов" })).toHaveAttribute("href", "/cases");
  });

  it("renders retryable route error instead of raw backend failure", async () => {
    fetchCaseDetailsMock
      .mockRejectedValueOnce(new ApiError("Internal Server Error", 503, "corr-case-503", null, "service_unavailable"))
      .mockResolvedValueOnce(detailsPayload);

    renderPage();

    expect(await screen.findByText("Карточка кейса временно недоступна")).toBeInTheDocument();
    expect(screen.getByText(/Код ошибки: 503/)).toBeInTheDocument();
    expect(screen.getByText(/Correlation ID: corr-case-503/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));

    expect(await screen.findByText("Проблема с лимитами")).toBeInTheDocument();
  });

  it("renders explicit empty states for timeline and snapshot gaps", async () => {
    fetchCaseDetailsMock.mockResolvedValue(detailsPayload);

    renderPage();

    expect(await screen.findByText("Проблема с лимитами")).toBeInTheDocument();
    expect(screen.getByText("История пока недоступна")).toBeInTheDocument();
    expect(screen.getByText("Снимок пока недоступен")).toBeInTheDocument();
  });
});

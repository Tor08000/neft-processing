import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/http";
import { SupportTicketDetailsPage } from "./SupportTicketDetailsPage";

const useAuthMock = vi.fn();
const fetchSupportTicketMock = vi.fn();
const fetchHelpdeskTicketLinkMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../api/supportTickets", () => ({
  fetchSupportTicket: (...args: unknown[]) => fetchSupportTicketMock(...args),
  createSupportTicketComment: vi.fn(),
  closeSupportTicket: vi.fn(),
}));

vi.mock("../api/helpdesk", () => ({
  fetchHelpdeskTicketLink: (...args: unknown[]) => fetchHelpdeskTicketLinkMock(...args),
}));

const session = {
  token: "header.eyJ1c2VyX2lkIjoidXNlci0xIn0=.sig",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const detailsPayload = {
  id: "ticket-1",
  org_id: "client-1",
  created_by_user_id: "user-1",
  subject: "Проблема с оплатой",
  message: "Нужна проверка платежа",
  status: "OPEN" as const,
  priority: "NORMAL" as const,
  first_response_due_at: "2025-01-01T12:00:00Z",
  first_response_at: null,
  resolution_due_at: "2025-01-02T12:00:00Z",
  resolved_at: null,
  sla_first_response_status: "PENDING" as const,
  sla_resolution_status: "PENDING" as const,
  sla_first_response_remaining_minutes: 60,
  sla_resolution_remaining_minutes: 120,
  case_id: "case-1",
  case_status: "TRIAGE" as const,
  case_queue: "SUPPORT" as const,
  case_priority: "MEDIUM" as const,
  case_updated_at: "2025-01-01T10:10:00Z",
  created_at: "2025-01-01T10:00:00Z",
  updated_at: "2025-01-01T10:10:00Z",
  comments: [],
};

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/client/support/ticket-1"]}>
      <Routes>
        <Route path="/client/support/:id" element={<SupportTicketDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("SupportTicketDetailsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({ user: session });
    fetchHelpdeskTicketLinkMock.mockResolvedValue({ link: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders explicit not-found state for a missing support ticket", async () => {
    fetchSupportTicketMock.mockRejectedValue(
      new ApiError("support_ticket_not_found", 404, "corr-ticket-404", null, "support_ticket_not_found"),
    );

    renderPage();

    expect(await screen.findByText("Обращение не найдено")).toBeInTheDocument();
    expect(screen.getByText("Проверьте номер обращения и попробуйте снова.")).toBeInTheDocument();
  });

  it("renders correlation-aware retry state instead of a raw support detail failure", async () => {
    fetchSupportTicketMock
      .mockRejectedValueOnce(new ApiError("Internal Server Error", 503, "corr-ticket-503", null, "service_unavailable"))
      .mockResolvedValueOnce(detailsPayload);

    renderPage();

    expect(await screen.findByText("Сервис временно недоступен")).toBeInTheDocument();
    expect(screen.getByText(/Код ошибки: 503/)).toBeInTheDocument();
    expect(screen.getByText(/Correlation ID: corr-ticket-503/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));

    expect(await screen.findByText("Проблема с оплатой")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "case-1" })).toHaveAttribute("href", "/cases/case-1");
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/http";
import { SupportTicketsPage } from "./SupportTicketsPage";

const useAuthMock = vi.fn();
const fetchSupportTicketsMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../api/supportTickets", () => ({
  fetchSupportTickets: (...args: unknown[]) => fetchSupportTicketsMock(...args),
}));

const session = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const sampleItem = {
  id: "ticket-1",
  org_id: "client-1",
  created_by_user_id: "user-1",
  subject: "Проблема с оплатой",
  message: "Нужна проверка",
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
};

describe("SupportTicketsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({ user: session });
  });

  it("renders first-use empty state when no support tickets exist yet", async () => {
    fetchSupportTicketsMock.mockResolvedValue({ items: [], next_cursor: null });

    render(
      <MemoryRouter>
        <SupportTicketsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Обращений пока нет")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Создать обращение" })).toEqual(
      expect.arrayContaining([expect.objectContaining({ href: expect.stringContaining("/client/support/new") })]),
    );
  });

  it("renders filtered empty state when filters hide all support tickets", async () => {
    fetchSupportTicketsMock.mockImplementation((_user: unknown, filters: { status?: string }) =>
      Promise.resolve({
        items: filters?.status === "CLOSED" ? [] : [sampleItem],
        next_cursor: null,
      }),
    );

    render(
      <MemoryRouter>
        <SupportTicketsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Проблема с оплатой")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Статус"), { target: { value: "CLOSED" } });

    expect(await screen.findByText("Обращения не найдены")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сбросить фильтры" })).toBeInTheDocument();
  });

  it("shows correlation-aware retry state for canonical support list failures", async () => {
    fetchSupportTicketsMock
      .mockRejectedValueOnce(new ApiError("Support contour unavailable", 503, "corr-support-list", null, "service_unavailable"))
      .mockResolvedValueOnce({ items: [sampleItem], next_cursor: null });

    render(
      <MemoryRouter>
        <SupportTicketsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Сервис временно недоступен")).toBeInTheDocument();
    expect(screen.getByText(/Код ошибки: 503/)).toBeInTheDocument();
    expect(screen.getByText(/Correlation ID: corr-support-list/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));

    expect(await screen.findByText("Проблема с оплатой")).toBeInTheDocument();
  });
});

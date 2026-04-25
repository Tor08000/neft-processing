import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/http";
import { CasesPage } from "./CasesPage";

const useAuthMock = vi.fn();
const fetchCasesMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../api/cases", () => ({
  fetchCases: (...args: unknown[]) => fetchCasesMock(...args),
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
  id: "case-1",
  tenant_id: 1,
  kind: "support" as const,
  entity_type: "support_ticket",
  entity_id: "ticket-1",
  title: "Проблема с лимитами",
  description: "Описание",
  status: "TRIAGE" as const,
  queue: "SUPPORT" as const,
  priority: "MEDIUM" as const,
  escalation_level: 0,
  first_response_due_at: "2025-01-01T12:00:00Z",
  resolve_due_at: "2025-01-02T12:00:00Z",
  created_at: "2025-01-01T10:00:00Z",
  updated_at: "2025-01-01T10:10:00Z",
  last_activity_at: "2025-01-01T10:10:00Z",
};

describe("CasesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({ user: session });
  });

  it("renders first-use empty state when the canonical owner has no cases yet", async () => {
    fetchCasesMock.mockResolvedValue({ items: [], total: 0, limit: 50, next_cursor: null });

    render(
      <MemoryRouter>
        <CasesPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Кейсов пока нет")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Создать обращение" })).toHaveAttribute("href", "/client/support/new");
  });

  it("renders filtered empty state when current filters hide all cases", async () => {
    fetchCasesMock.mockImplementation((_user: unknown, params: { status?: string }) =>
      Promise.resolve({
        items: params?.status === "CLOSED" ? [] : [sampleItem],
        total: params?.status === "CLOSED" ? 0 : 1,
        limit: 50,
        next_cursor: null,
      }),
    );

    render(
      <MemoryRouter>
        <CasesPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Проблема с лимитами")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Статус"), { target: { value: "CLOSED" } });

    expect(await screen.findByText("Кейсы не найдены")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сбросить фильтры" })).toBeInTheDocument();
  });

  it("shows retryable canonical error state instead of a raw failure", async () => {
    fetchCasesMock
      .mockRejectedValueOnce(new ApiError("Service Unavailable", 503, "corr-cases-1", null, "service_unavailable"))
      .mockResolvedValueOnce({ items: [sampleItem], total: 1, limit: 50, next_cursor: null });

    render(
      <MemoryRouter>
        <CasesPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Контур кейсов временно недоступен")).toBeInTheDocument();
    expect(screen.getByText(/Код ошибки: 503/)).toBeInTheDocument();
    expect(screen.getByText(/Correlation ID: corr-cases-1/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));

    expect(await screen.findByText("Проблема с лимитами")).toBeInTheDocument();
  });
});

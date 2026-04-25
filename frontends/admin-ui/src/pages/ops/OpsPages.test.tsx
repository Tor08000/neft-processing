import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EscalationsPage from "./EscalationsPage";
import KpiPage from "./KpiPage";
import OpsOverviewPage from "./OpsOverviewPage";

const { useAuthMock, showToastMock, fetchOpsSummaryMock, requestMock, MockApiError } = vi.hoisted(() => {
  class HoistedMockApiError extends Error {
    status: number;
    requestId: string | null;
    correlationId: string | null;
    errorCode: string | null;

    constructor(
      message: string,
      status: number,
      requestId: string | null = null,
      correlationId: string | null = null,
      errorCode: string | null = null,
    ) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.requestId = requestId;
      this.correlationId = correlationId;
      this.errorCode = errorCode;
    }
  }

  return {
    useAuthMock: vi.fn(),
    showToastMock: vi.fn(),
    fetchOpsSummaryMock: vi.fn(),
    requestMock: vi.fn(),
    MockApiError: HoistedMockApiError,
  };
});

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../../components/Toast/useToast", () => ({
  useToast: () => ({
    toast: null,
    showToast: showToastMock,
  }),
}));

vi.mock("../../components/common/Toast", () => ({
  Toast: () => null,
}));

vi.mock("../../components/common/DateRangePicker", () => ({
  DateRangePicker: () => <div>DateRangePicker</div>,
}));

vi.mock("../../components/ops/ReasonModal", () => ({
  ReasonModal: () => null,
}));

vi.mock("../../components/ops/EscalationRow", () => ({
  EscalationRow: ({
    item,
    onSelect,
  }: {
    item: { id: string; subject_id: string; status: string };
    onSelect: (id: string) => void;
  }) => (
    <tr>
      <td>
        <button type="button" onClick={() => onSelect(item.id)}>
          {item.id}
        </button>
      </td>
      <td>{item.subject_id}</td>
      <td>{item.status}</td>
    </tr>
  ),
}));

vi.mock("../../api/ops", () => ({
  fetchOpsSummary: (...args: unknown[]) => fetchOpsSummaryMock(...args),
}));

vi.mock("../../api/http", () => ({
  request: (...args: unknown[]) => requestMock(...args),
  ApiError: MockApiError,
}));

vi.mock("../admin/AdminStatusPages", () => ({
  AdminMisconfigPage: ({ requestId, errorId }: { requestId?: string; errorId?: string }) => (
    <div>
      Misconfig {requestId} {errorId}
    </div>
  ),
}));

vi.mock("./OpsSignalsPanel", () => ({
  default: () => <div>signals-panel</div>,
}));

vi.mock("./OpsQueuesPanel", () => ({
  default: () => <div>queues-panel</div>,
}));

vi.mock("./OpsMorPanel", () => ({
  default: () => <div>mor-panel</div>,
}));

vi.mock("./OpsBillingPanel", () => ({
  default: () => <div>billing-panel</div>,
}));

vi.mock("./OpsReconciliationPanel", () => ({
  default: () => <div>reconciliation-panel</div>,
}));

vi.mock("./OpsExportsPanel", () => ({
  default: () => <div>exports-panel</div>,
}));

vi.mock("./OpsSupportPanel", () => ({
  default: () => <div>support-panel</div>,
}));

describe("Ops operator pages", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "admin-token" });
  });

  it("shows retryable error state on ops overview load failure and recovers on retry", async () => {
    fetchOpsSummaryMock
      .mockRejectedValueOnce(new Error("summary unavailable"))
      .mockResolvedValueOnce({
        env: { name: "dev", build: "build-1" },
        time: { now: "2026-04-19T12:00:00Z" },
        signals: {},
        queues: {},
        mor: {},
        billing: {},
        reconciliation: {},
        exports: {},
        support: {},
      });

    render(
      <MemoryRouter>
        <OpsOverviewPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Failed to load ops summary")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(fetchOpsSummaryMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("signals-panel")).toBeInTheDocument();
  });

  it("shows empty KPI state when the selected period has no data", async () => {
    requestMock.mockResolvedValue({
      by_reason: {},
      by_team: {},
    });

    render(
      <MemoryRouter>
        <KpiPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("No KPI data for the selected period")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Refresh" })).toHaveLength(2);
  });

  it("shows retryable KPI error state with request metadata", async () => {
    requestMock.mockRejectedValue(
      new MockApiError("kpi unavailable", 503, "req-kpi", "corr-kpi"),
    );

    render(
      <MemoryRouter>
        <KpiPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Failed to load KPI summary")).toBeInTheDocument();
    expect(screen.getByText(/request_id: req-kpi/i)).toBeInTheDocument();
    expect(screen.getByText(/correlation_id: corr-kpi/i)).toBeInTheDocument();
  });

  it("shows filtered-empty reset flow on escalations", async () => {
    requestMock
      .mockResolvedValueOnce({
        items: [
          {
            id: "esc-1",
            client_id: "client-1",
            target: "CRM",
            status: "OPEN",
            priority: "HIGH",
            primary_reason: "LIMIT",
            reason_code: "LIMIT_BLOCK",
            subject_type: "ORDER",
            subject_id: "order-1",
            sla_expires_at: null,
            sla_started_at: null,
            sla_due_at: null,
            sla_overdue: false,
            sla_elapsed_seconds: null,
            created_at: "2026-04-19T12:00:00Z",
            acked_at: null,
            acked_by: null,
            ack_reason_code: null,
            ack_reason_text: null,
            closed_at: null,
            closed_by: null,
            close_reason_code: null,
            close_reason_text: null,
            unified_explain_snapshot_hash: null,
            unified_explain_snapshot: null,
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: "esc-1",
            client_id: "client-1",
            target: "CRM",
            status: "OPEN",
            priority: "HIGH",
            primary_reason: "LIMIT",
            reason_code: "LIMIT_BLOCK",
            subject_type: "ORDER",
            subject_id: "order-1",
            sla_expires_at: null,
            sla_started_at: null,
            sla_due_at: null,
            sla_overdue: false,
            sla_elapsed_seconds: null,
            created_at: "2026-04-19T12:00:00Z",
            acked_at: null,
            acked_by: null,
            ack_reason_code: null,
            ack_reason_text: null,
            closed_at: null,
            closed_by: null,
            close_reason_code: null,
            close_reason_text: null,
            unified_explain_snapshot_hash: null,
            unified_explain_snapshot: null,
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      });

    render(
      <MemoryRouter>
        <EscalationsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Escalation esc-1")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "CLOSED" } });

    expect(await screen.findByText("No escalations match current filters")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Reset filters" })[1]);

    expect(await screen.findByText("Escalation esc-1")).toBeInTheDocument();
  });
});

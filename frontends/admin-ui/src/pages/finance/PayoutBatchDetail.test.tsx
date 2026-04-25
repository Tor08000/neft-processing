import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import PayoutBatchDetail from "./PayoutBatchDetail";
import * as payoutsApi from "../../api/payouts";

vi.mock("../../api/payouts", () => ({
  fetchPayoutBatchDetails: vi.fn(),
  reconcilePayoutBatch: vi.fn(),
  markPayoutSent: vi.fn(),
  markPayoutSettled: vi.fn(),
}));

vi.mock("../../components/Toast/Toast", () => ({
  Toast: () => null,
}));

vi.mock("../../components/Toast/useToast", () => ({
  useToast: () => ({
    toast: null,
    showToast: vi.fn(),
  }),
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/finance/payout-batches/batch-1"]}>
        <Routes>
          <Route path="/finance/payout-batches/:batchId" element={<PayoutBatchDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PayoutBatchDetail", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the extracted empty-state copy when a batch has no items", async () => {
    (payoutsApi.fetchPayoutBatchDetails as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "batch-1",
      tenant_id: 1,
      partner_id: "partner-1",
      date_from: "2026-04-01",
      date_to: "2026-04-15",
      state: "READY",
      total_amount: 0,
      total_qty: 0,
      operations_count: 0,
      created_at: "2026-04-15T10:00:00Z",
      sent_at: null,
      settled_at: null,
      provider: null,
      external_ref: null,
      items: [],
    });

    renderPage();

    expect(await screen.findByText(/Payout batch/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Нет позиций")).toBeInTheDocument());
    expect(screen.getByText("В этом батче пока нет операций.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Обновить" })).toBeInTheDocument();
  });
});

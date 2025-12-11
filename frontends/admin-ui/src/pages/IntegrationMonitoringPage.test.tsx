import { describe, expect, it, vi, beforeEach } from "vitest";
import type { Mock } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import IntegrationMonitoringPage from "./IntegrationMonitoringPage";
import * as api from "../api/integrationMonitoring";

vi.mock("../api/integrationMonitoring", () => ({
  fetchPartnerStatuses: vi.fn(),
  fetchAzsHeatmap: vi.fn(),
  fetchIntegrationRequests: vi.fn(),
  fetchRecentDeclines: vi.fn(),
}));

describe("IntegrationMonitoringPage", () => {
  beforeEach(() => {
    (api.fetchPartnerStatuses as unknown as Mock).mockResolvedValue({ items: [{ partner_id: "p1", partner_name: "P1", status: "ONLINE", total_requests: 2, error_rate: 0, avg_latency_ms: 10 }] });
    (api.fetchAzsHeatmap as unknown as Mock).mockResolvedValue({ items: [{ azs_id: "azs-1", total_requests: 2, declines_total: 1, declines_by_category: {}, error_rate: 0.1 }] });
    (api.fetchIntegrationRequests as unknown as Mock).mockResolvedValue({ items: [{ id: 1, created_at: new Date().toISOString(), partner_id: "p1", azs_id: "azs-1", request_type: "AUTHORIZE", amount: 100, status: "APPROVED", reason_category: null }], total: 1 });
    (api.fetchRecentDeclines as unknown as Mock).mockResolvedValue({ items: [{ id: 2, created_at: new Date().toISOString(), partner_id: "p1", azs_id: "azs-1", reason_category: "RISK", amount: 10 }] });
  });

  it("renders all sections and reacts to filters", async () => {
    render(
      <MemoryRouter>
        <IntegrationMonitoringPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Partner Status")).toBeInTheDocument());
    expect(screen.getByText("AZS Heatmap")).toBeInTheDocument();
    expect(screen.getByText("Incoming Requests")).toBeInTheDocument();
    expect(screen.getByText(/Realtime Declines/)).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Partner"), { target: { value: "p1" } });
    await waitFor(() => expect(api.fetchIntegrationRequests).toHaveBeenCalled());
  });
});

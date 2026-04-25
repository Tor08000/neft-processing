import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ApiError } from "../../api/http";
import AuditPage from "./AuditPage";

const useAuthMock = vi.fn();
const fetchAuditFeedMock = vi.fn();
const fetchAuditCorrelationMock = vi.fn();

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../../api/audit", () => ({
  fetchAuditFeed: (...args: unknown[]) => fetchAuditFeedMock(...args),
  fetchAuditCorrelation: (...args: unknown[]) => fetchAuditCorrelationMock(...args),
}));

vi.mock("../../components/CopyButton/CopyButton", () => ({
  CopyButton: ({ label }: { label: string }) => <button type="button">{label}</button>,
}));

const renderPage = (entry = "/audit?entity_type=admin_user&entity_id=admin-500") => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/audit/:correlationId" element={<AuditPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("AuditPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "admin-token" });
    fetchAuditCorrelationMock.mockResolvedValue({ correlation_id: "corr-admin-500", items: [] });
  });

  it("renders admin-user scoped view and deep links from canonical audit data", async () => {
    fetchAuditFeedMock.mockResolvedValue({
      items: [
        {
          id: "evt-1",
          title: "ADMIN_USER_UPDATED",
          type: "ADMIN_USER_UPDATED",
          entity_type: "admin_user",
          entity_id: "admin-500",
          correlation_id: "corr-admin-500",
          reason: "Rotate support coverage",
          ts: "2026-04-13T12:00:00Z",
        },
      ],
      total: 1,
    });

    renderPage();

    expect(await screen.findByText("Scoped audit view")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open admin profile" })).toHaveAttribute("href", "/admins/admin-500");
    expect(await screen.findByText("ADMIN_USER_UPDATED")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Admin profile" })).toHaveAttribute("href", "/admins/admin-500");
    expect(screen.getByRole("link", { name: "Filter entity" })).toHaveAttribute(
      "href",
      "/audit?entity_type=admin_user&entity_id=admin-500",
    );
  });

  it("shows a retryable error state for non-404 feed failures and recovers on retry", async () => {
    const user = userEvent.setup();
    fetchAuditFeedMock
      .mockRejectedValueOnce(
        new ApiError("owner route unavailable", 503, "req-audit-500", "corr-audit-500", "service_unavailable"),
      )
      .mockResolvedValueOnce({
        items: [
          {
            id: "evt-2",
            title: "ADMIN_USER_RECOVERED",
            type: "ADMIN_USER_RECOVERED",
            entity_type: "admin_user",
            entity_id: "admin-500",
            ts: "2026-04-13T13:00:00Z",
          },
        ],
        total: 1,
      });

    renderPage();

    expect(await screen.findByText("Failed to load audit feed")).toBeInTheDocument();
    expect(screen.getByText("owner route unavailable")).toBeInTheDocument();
    expect(screen.getByText("request_id: req-audit-500 | correlation_id: corr-audit-500")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("ADMIN_USER_RECOVERED")).toBeInTheDocument();
  });

  it("shows a filtered-empty state when the audit slice is mounted but has no matching events", async () => {
    fetchAuditFeedMock.mockResolvedValue({ items: [], total: 0 });

    renderPage("/audit?search=partner-77");

    expect(await screen.findByText("Audit events not found")).toBeInTheDocument();
    expect(
      screen.getByText("Adjust the audit filters or refresh the feed to inspect a different operator slice."),
    ).toBeInTheDocument();
  });
});

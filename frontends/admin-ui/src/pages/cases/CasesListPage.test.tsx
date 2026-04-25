import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import CasesListPage from "./CasesListPage";
import * as casesApi from "../../api/cases";
import * as adminCasesApi from "../../api/adminCases";
import { buildAdminPermissions } from "../../admin/access";

const useAdminMock = vi.fn();

vi.mock("../../api/cases", () => ({
  fetchCases: vi.fn(),
}));

vi.mock("../../api/adminCases", () => ({
  closeAdminCase: vi.fn(),
  isNotAvailableError: vi.fn(() => false),
}));

vi.mock("../../admin/AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

describe("CasesListPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["NEFT_SUPPORT"]),
        read_only: false,
      },
    });
    (casesApi.fetchCases as unknown as Mock).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      next_cursor: null,
    });
    (adminCasesApi.closeAdminCase as unknown as Mock).mockResolvedValue(undefined);
  });

  it("renders empty state", async () => {
    render(
      <MemoryRouter>
        <CasesListPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("No cases found")).toBeInTheDocument());
    expect(screen.getByText("Cases")).toBeInTheDocument();
  });

  it("renders support-specific empty state when queue is scoped to support", async () => {
    render(
      <MemoryRouter initialEntries={["/cases?queue=SUPPORT"]}>
        <CasesListPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Support queue is empty")).toBeInTheDocument());
    expect(screen.getByText("Support & Incident Inbox")).toBeInTheDocument();
  });

  it("keeps close action disabled for cases read-only roles", async () => {
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["NEFT_FINANCE"]),
        read_only: false,
      },
    });
    (casesApi.fetchCases as unknown as Mock).mockResolvedValue({
      items: [
        {
          id: "case-readonly",
          tenant_id: 1,
          kind: "incident",
          title: "Incident requiring support",
          status: "TRIAGE",
          queue: "SUPPORT",
          priority: "HIGH",
          escalation_level: 0,
          created_at: "2026-04-23T10:00:00Z",
          updated_at: "2026-04-23T10:00:00Z",
          last_activity_at: "2026-04-23T10:00:00Z",
        },
      ],
      total: 1,
      limit: 20,
      next_cursor: null,
    });

    render(
      <MemoryRouter>
        <CasesListPage />
      </MemoryRouter>,
    );

    const closeButton = await screen.findByRole("button", { name: "Close" });
    expect(closeButton).toBeDisabled();
    expect(closeButton).toHaveAttribute("title", "Requires cases operate capability");
  });
});

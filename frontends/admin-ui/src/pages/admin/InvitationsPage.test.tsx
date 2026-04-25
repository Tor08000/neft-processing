import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import InvitationsPage from "./InvitationsPage";
import * as invitationsApi from "../../api/invitations";

vi.mock("../../api/invitations", () => ({
  listAdminInvitations: vi.fn(),
  resendInvitation: vi.fn(),
  revokeInvitation: vi.fn(),
}));

describe("InvitationsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    (invitationsApi.listAdminInvitations as unknown as Mock).mockResolvedValue({
      items: [
        {
          invitation_id: "invite-1",
          email: "manager@example.com",
          role: "CLIENT_MANAGER",
          status: "PENDING",
          created_at: "2026-04-10T10:00:00Z",
          expires_at: "2026-04-17T10:00:00Z",
          resent_count: 1,
        },
      ],
      total: 1,
    });
  });

  it("loads the canonical admin onboarding inbox without requiring client_id", async () => {
    render(<InvitationsPage />);

    await waitFor(() => expect(invitationsApi.listAdminInvitations).toHaveBeenCalled());
    expect(invitationsApi.listAdminInvitations).toHaveBeenCalledWith({
      client_id: undefined,
      status: "ALL",
      q: undefined,
      sort: "created_at_desc",
    });
    expect(screen.getByText("Canonical onboarding/admin invitation inbox. `client_id` is now an optional filter, not a required lookup key.")).toBeInTheDocument();
    expect(screen.getByText("manager@example.com")).toBeInTheDocument();
    expect(screen.getByText("Total: 1")).toBeInTheDocument();
  });

  it("shows filtered-empty reset state for invitation search", async () => {
    (invitationsApi.listAdminInvitations as unknown as Mock)
      .mockResolvedValueOnce({
        items: [
          {
            invitation_id: "invite-1",
            email: "manager@example.com",
            role: "CLIENT_MANAGER",
            status: "PENDING",
            created_at: "2026-04-10T10:00:00Z",
            expires_at: "2026-04-17T10:00:00Z",
            resent_count: 1,
          },
        ],
        total: 1,
      })
      .mockResolvedValueOnce({
        items: [],
        total: 0,
      })
      .mockResolvedValueOnce({
        items: [
          {
            invitation_id: "invite-1",
            email: "manager@example.com",
            role: "CLIENT_MANAGER",
            status: "PENDING",
            created_at: "2026-04-10T10:00:00Z",
            expires_at: "2026-04-17T10:00:00Z",
            resent_count: 1,
          },
        ],
        total: 1,
      });

    render(<InvitationsPage />);

    expect(await screen.findByText("manager@example.com")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("email"), { target: { value: "missing@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByText("Invitations not found")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Reset filters" })[1]);

    expect(await screen.findByText("manager@example.com")).toBeInTheDocument();
  });
});

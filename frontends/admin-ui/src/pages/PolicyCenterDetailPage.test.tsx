import { describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import PolicyCenterDetailPage from "./PolicyCenterDetailPage";
import * as policiesApi from "../api/policies";
import { ForbiddenError } from "../api/http";

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "token" }),
}));

vi.mock("../api/policies", () => ({
  fetchPolicyDetail: vi.fn(),
  fetchPolicyExecutions: vi.fn(),
  enablePolicy: vi.fn(),
  disablePolicy: vi.fn(),
}));

describe("PolicyCenterDetailPage", () => {
  it("renders policy detail for deep link", async () => {
    (policiesApi.fetchPolicyDetail as unknown as Mock).mockResolvedValue({
      header: {
        id: "policy-1",
        type: "fleet",
        title: "LIMIT_BREACH → AUTO_BLOCK_CARD",
        status: "enabled",
        scope: { tenant_id: null, client_id: "client-1" },
        actions: ["AUTO_BLOCK_CARD"],
        updated_at: null,
        toggle_supported: true,
      },
      policy: { id: "policy-1" },
      explain: null,
    });
    (policiesApi.fetchPolicyExecutions as unknown as Mock).mockResolvedValue({ items: [] });

    render(
      <MemoryRouter initialEntries={["/policies/fleet/policy-1"]}>
        <Routes>
          <Route path="/policies/:type/:id" element={<PolicyCenterDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("LIMIT_BREACH → AUTO_BLOCK_CARD")).toBeInTheDocument());
    expect(screen.getByText("Policy ID: policy-1")).toBeInTheDocument();
  });

  it("renders a retryable error state when policy detail is unavailable", async () => {
    (policiesApi.fetchPolicyDetail as unknown as Mock).mockRejectedValue(new Error("policy_not_found"));
    (policiesApi.fetchPolicyExecutions as unknown as Mock).mockResolvedValue({ items: [] });

    render(
      <MemoryRouter initialEntries={["/policies/fleet/missing"]}>
        <Routes>
          <Route path="/policies/:type/:id" element={<PolicyCenterDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Policy detail is unavailable.")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Back to list" })).toHaveAttribute("href", "/policies");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("uses the canonical admin forbidden state for denied policy detail access", async () => {
    (policiesApi.fetchPolicyDetail as unknown as Mock).mockRejectedValue(new ForbiddenError());
    (policiesApi.fetchPolicyExecutions as unknown as Mock).mockResolvedValue({ items: [] });

    render(
      <MemoryRouter initialEntries={["/policies/fleet/policy-1"]}>
        <Routes>
          <Route path="/policies/:type/:id" element={<PolicyCenterDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("FORBIDDEN_ROLE")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/");
  });
});

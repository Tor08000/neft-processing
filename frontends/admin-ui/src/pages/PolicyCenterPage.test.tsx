import { describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import PolicyCenterPage from "./PolicyCenterPage";
import * as policiesApi from "../api/policies";

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "token" }),
}));

vi.mock("../api/policies", () => ({
  listPolicies: vi.fn(),
}));

describe("PolicyCenterPage", () => {
  it("renders empty state when no policies", async () => {
    (policiesApi.listPolicies as unknown as Mock).mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });

    render(
      <MemoryRouter>
        <PolicyCenterPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Policy Center")).toBeInTheDocument());
    expect(screen.getByText("No policies found")).toBeInTheDocument();
  });

  it("renders filters without crashing", async () => {
    (policiesApi.listPolicies as unknown as Mock).mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });

    render(
      <MemoryRouter>
        <PolicyCenterPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Type")).toBeInTheDocument());
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("title / id / action")).toBeInTheDocument();
  });
});

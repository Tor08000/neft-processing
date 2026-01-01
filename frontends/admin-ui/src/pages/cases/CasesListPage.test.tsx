import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import CasesListPage from "./CasesListPage";
import * as adminCasesApi from "../../api/adminCases";

vi.mock("../../api/adminCases", () => ({
  fetchAdminCases: vi.fn(),
  closeAdminCase: vi.fn(),
  isNotAvailableError: vi.fn(() => false),
}));

describe("CasesListPage", () => {
  beforeEach(() => {
    (adminCasesApi.fetchAdminCases as unknown as Mock).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      next_cursor: null,
    });
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
});

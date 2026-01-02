import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import ReconciliationStatementsPage from "./ReconciliationStatementsPage";
import * as reconciliationApi from "../../api/reconciliation";

vi.mock("../../api/reconciliation", () => ({
  listStatements: vi.fn(),
  uploadStatement: vi.fn(),
  createExternalRun: vi.fn(),
}));

describe("ReconciliationStatementsPage", () => {
  beforeEach(() => {
    (reconciliationApi.listStatements as unknown as Mock).mockResolvedValue({ statements: [] });
    (reconciliationApi.uploadStatement as unknown as Mock).mockResolvedValue({ statement: null });
  });

  it("validates upload modal", async () => {
    render(
      <MemoryRouter>
        <ReconciliationStatementsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Upload statement")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Upload statement"));

    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "Bank" } });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "USD" } });
    fireEvent.change(screen.getByLabelText("Period start"), { target: { value: "2024-01-01T00:00" } });
    fireEvent.change(screen.getByLabelText("Period end"), { target: { value: "2024-01-02T00:00" } });
    fireEvent.change(screen.getByLabelText("Lines JSON"), { target: { value: "{invalid" } });

    fireEvent.click(screen.getByText("Upload"));

    await waitFor(() => expect(screen.getByText("Lines must be valid JSON")).toBeInTheDocument());
  });
});

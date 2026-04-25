import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { DashboardRenderer } from "./DashboardRenderer";

const dashboard = {
  role: "ACCOUNTANT",
  timezone: "Europe/Moscow",
  widgets: [
    {
      type: "list",
      key: "recent_documents",
      data: [{ id: "doc-1", type: "ACT", status: "ISSUED", date: "2026-04-01" }],
    },
    {
      type: "cta",
      key: "accountant_actions",
      data: null,
    },
  ],
} as const;

describe("DashboardRenderer documents entry points", () => {
  it("keeps generic documents discovery on the canonical /client/documents contour", () => {
    render(
      <MemoryRouter>
        <DashboardRenderer dashboard={dashboard} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Перейти" })).toHaveAttribute("href", "/client/documents");
    expect(screen.getByRole("link", { name: "Документы" })).toHaveAttribute("href", "/client/documents");
    expect(screen.queryByRole("link", { name: "/documents/i" })).not.toBeInTheDocument();
  });
});

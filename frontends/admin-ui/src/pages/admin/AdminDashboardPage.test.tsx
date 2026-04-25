import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import AdminDashboardPage from "./AdminDashboardPage";
import { buildAdminPermissions } from "../../admin/access";

const useAdminMock = vi.fn();

vi.mock("../../admin/AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

describe("AdminDashboardPage", () => {
  it("renders a strict operator console with mounted surfaces and visibility map", () => {
    useAdminMock.mockReturnValue({
      profile: {
        primary_role_level: "platform_admin",
        role_levels: ["platform_admin", "finance_admin"],
        env: { name: "stage" },
        read_only: false,
        audit_context: { require_reason: true, require_correlation_id: true },
        permissions: buildAdminPermissions(["PLATFORM_ADMIN", "NEFT_FINANCE"]),
      },
    });

    render(
      <MemoryRouter>
        <AdminDashboardPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Admin operator console" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Primary operator routes" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cases" })).toHaveAttribute("href", "/cases?queue=SUPPORT");
    expect(screen.getByRole("link", { name: /commercial finance read surface/ })).toHaveAttribute(
      "href",
      "/finance/revenue",
    );
    expect(screen.getByRole("link", { name: /Rules Sandbox/ })).toHaveAttribute("href", "/rules/sandbox");
    expect(screen.getByRole("link", { name: /Risk Rules/ })).toHaveAttribute("href", "/risk/rules");
    expect(screen.getByRole("link", { name: /Policy Center/ })).toHaveAttribute("href", "/policies");
    expect(screen.getByRole("link", { name: /Legal documents/ })).toHaveAttribute("href", "/legal/documents");
    expect(screen.getByRole("link", { name: /Legal partners/ })).toHaveAttribute("href", "/legal/partners");
    expect(screen.getByRole("heading", { name: "Capability visibility map" })).toBeInTheDocument();
    const hrefs = screen.getAllByRole("link").map((link) => link.getAttribute("href") ?? "");
    expect(hrefs.some((href) => href.startsWith("/billing"))).toBe(false);
    expect(hrefs.some((href) => href.startsWith("/money"))).toBe(false);
    expect(hrefs.some((href) => href.startsWith("/fleet"))).toBe(false);
    expect(hrefs.some((href) => href.startsWith("/subscriptions"))).toBe(false);
    expect(hrefs.some((href) => href.startsWith("/operations"))).toBe(false);
    expect(hrefs.some((href) => href.startsWith("/explain"))).toBe(false);
  });
});

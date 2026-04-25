import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen } from "@testing-library/react";

import { buildAdminPermissions } from "./access";
import AdminShell from "./AdminShell";

const useAdminMock = vi.fn();

vi.mock("./AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

vi.mock("@shared/brand/components", () => ({
  BrandSidebar: ({ items, title }: { items: Array<{ label: string; to: string }>; title: string }) => (
    <nav>
      <div>{title}</div>
      {items.map((item) => (
        <a key={item.to} href={item.to}>
          {item.label}
        </a>
      ))}
    </nav>
  ),
  BrandHeader: ({
    title,
    subtitle,
    userSlot,
  }: {
    title: string;
    subtitle: string;
    userSlot?: React.ReactNode;
  }) => (
    <header>
      <h1>{title}</h1>
      <div>{subtitle}</div>
      {userSlot}
    </header>
  ),
  PageShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DashboardIcon: () => <span aria-hidden>dashboard</span>,
  UsersIcon: () => <span aria-hidden>users</span>,
  WorkflowIcon: () => <span aria-hidden>workflow</span>,
  WalletIcon: () => <span aria-hidden>wallet</span>,
  BriefcaseIcon: () => <span aria-hidden>briefcase</span>,
  ShieldIcon: () => <span aria-hidden>shield</span>,
  FileIcon: () => <span aria-hidden>file</span>,
  LogisticsIcon: () => <span aria-hidden>logistics</span>,
  ChartIcon: () => <span aria-hidden>chart</span>,
  AuditIcon: () => <span aria-hidden>audit</span>,
}));

describe("AdminShell", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows only canonical surfaces allowed by the admin capability model", () => {
    useAdminMock.mockReturnValue({
      profile: {
        admin_user: { email: "support@neft.test", roles: ["NEFT_SUPPORT"] },
        permissions: buildAdminPermissions(["NEFT_SUPPORT"]),
        role_levels: ["support_admin"],
        read_only: false,
      },
    });

    render(
      <MemoryRouter initialEntries={["/cases"]}>
        <Routes>
          <Route element={<AdminShell />}>
            <Route path="/cases" element={<div>Cases screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Cases" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Onboarding" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Marketplace" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Commercial" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Revenue" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admins" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "CRM" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Geo Analytics" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Rules Sandbox" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Risk Rules" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Policy Center" })).not.toBeInTheDocument();
    expect(screen.getByText("support_admin")).toBeInTheDocument();
  });

  it("marks read-only observers without exposing write-first navigation", () => {
    useAdminMock.mockReturnValue({
      profile: {
        admin_user: { email: "observer@neft.test", roles: ["OBSERVER"] },
        permissions: buildAdminPermissions(["OBSERVER"]),
        role_levels: ["observer"],
        read_only: true,
      },
    });

    render(
      <MemoryRouter initialEntries={["/audit"]}>
        <Routes>
          <Route element={<AdminShell />}>
            <Route path="/audit" element={<div>Audit screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("READ-ONLY")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Runtime" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Audit" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Revenue" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Onboarding" })).not.toBeInTheDocument();
  });

  it("mounts logistics and canonical legal entrypoints for operator-grade navigation", () => {
    useAdminMock.mockReturnValue({
      profile: {
        admin_user: { email: "ops@neft.test", roles: ["NEFT_OPS", "NEFT_LEGAL"] },
        permissions: buildAdminPermissions(["NEFT_OPS", "NEFT_LEGAL"]),
        role_levels: ["operator", "legal_admin"],
        read_only: false,
      },
    });

    render(
      <MemoryRouter initialEntries={["/logistics/inspection"]}>
        <Routes>
          <Route element={<AdminShell />}>
            <Route path="/logistics/inspection" element={<div>Inspection screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Logistics" })).toHaveAttribute("href", "/logistics/inspection");
    expect(screen.getByRole("link", { name: "Rules Sandbox" })).toHaveAttribute("href", "/rules/sandbox");
    expect(screen.getByRole("link", { name: "Risk Rules" })).toHaveAttribute("href", "/risk/rules");
    expect(screen.getByRole("link", { name: "Policy Center" })).toHaveAttribute("href", "/policies");
    expect(screen.getByRole("link", { name: "Legal" })).toHaveAttribute("href", "/legal/documents");
    expect(screen.queryByRole("link", { name: "Revenue" })).not.toBeInTheDocument();
  });

  it("shows admin management navigation only for access-managing roles", () => {
    useAdminMock.mockReturnValue({
      profile: {
        admin_user: { email: "platform@neft.test", roles: ["PLATFORM_ADMIN"] },
        permissions: buildAdminPermissions(["PLATFORM_ADMIN"]),
        role_levels: ["platform_admin"],
        read_only: false,
      },
    });

    render(
      <MemoryRouter initialEntries={["/admins"]}>
        <Routes>
          <Route element={<AdminShell />}>
            <Route path="/admins" element={<div>Admins screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Admins" })).toHaveAttribute("href", "/admins");
    expect(screen.queryByRole("link", { name: "Revenue" })).not.toBeInTheDocument();
    expect(screen.getByText("platform_admin")).toBeInTheDocument();
  });

  it("shows the revenue surface only to explicit revenue-capable finance and commercial roles", () => {
    useAdminMock.mockReturnValue({
      profile: {
        admin_user: { email: "finance@neft.test", roles: ["NEFT_FINANCE"] },
        permissions: buildAdminPermissions(["NEFT_FINANCE"]),
        role_levels: ["finance_admin"],
        read_only: false,
      },
    });

    render(
      <MemoryRouter initialEntries={["/finance/revenue"]}>
        <Routes>
          <Route element={<AdminShell />}>
            <Route path="/finance/revenue" element={<div>Revenue screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Revenue" })).toHaveAttribute("href", "/finance/revenue");
    expect(screen.getByRole("heading", { name: "Revenue" })).toBeInTheDocument();
    expect(screen.getByText("finance_admin")).toBeInTheDocument();
  });

  it("keeps section headers aligned for nested CRM and legal routes", () => {
    useAdminMock.mockReturnValue({
      profile: {
        admin_user: { email: "commercial@neft.test", roles: ["NEFT_SALES", "NEFT_LEGAL"] },
        permissions: buildAdminPermissions(["NEFT_SALES", "NEFT_LEGAL"]),
        role_levels: ["commercial_admin", "legal_admin"],
        read_only: false,
      },
    });

    const firstRender = render(
      <MemoryRouter initialEntries={["/crm/tariffs"]}>
        <Routes>
          <Route element={<AdminShell />}>
            <Route path="/crm/tariffs" element={<div>Tariffs screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "CRM" })).toBeInTheDocument();
    firstRender.unmount();

    render(
      <MemoryRouter initialEntries={["/legal/partners"]}>
        <Routes>
          <Route element={<AdminShell />}>
            <Route path="/legal/partners" element={<div>Partners screen</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Legal" })).toBeInTheDocument();
  });
});

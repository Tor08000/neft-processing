import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ClientTopbar } from "./ClientTopbar";

const baseProps = {
  title: "Client portal",
  activePath: "/dashboard",
  items: [{ to: "/dashboard", label: "Overview", icon: <span>i</span>, audience: "all" as const }],
  userEmail: "user@test.dev",
  mode: "personal" as const,
  theme: "light" as const,
  onToggleTheme: vi.fn(),
  onToggleSidebar: vi.fn(),
  onLogout: vi.fn(),
};

describe("ClientTopbar mode indicator", () => {
  it("renders the system-derived mode as a read-only indicator", () => {
    render(
      <MemoryRouter>
        <ClientTopbar {...baseProps} />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("client-mode-indicator")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("does not expose a manual client kind switcher for fleet-capable users", () => {
    render(
      <MemoryRouter>
        <ClientTopbar {...baseProps} mode="fleet" />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("client-mode-indicator")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});

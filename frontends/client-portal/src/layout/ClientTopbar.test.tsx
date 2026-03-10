import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ClientTopbar } from "./ClientTopbar";

const baseProps = {
  title: "Клиентский портал",
  activePath: "/dashboard",
  items: [{ to: "/dashboard", label: "Обзор", icon: <span>i</span>, audience: "all" as const }],
  userEmail: "user@test.dev",
  mode: "personal" as const,
  theme: "light" as const,
  onSelectMode: vi.fn(),
  onToggleTheme: vi.fn(),
  onToggleSidebar: vi.fn(),
  onLogout: vi.fn(),
};

describe("ClientTopbar mode switcher", () => {
  it("does not render mode switcher for single-mode users", () => {
    render(
      <MemoryRouter>
        <ClientTopbar {...baseProps} availableModes={["personal"]} />
      </MemoryRouter>,
    );

    expect(screen.queryByLabelText("Режим клиента")).not.toBeInTheDocument();
  });

  it("allows switching between allowed modes for multi-mode users", () => {
    const onSelectMode = vi.fn();
    render(
      <MemoryRouter>
        <ClientTopbar
          {...baseProps}
          availableModes={["personal", "fleet"]}
          onSelectMode={onSelectMode}
        />
      </MemoryRouter>,
    );

    const select = screen.getByLabelText("Режим клиента");
    fireEvent.change(select, { target: { value: "fleet" } });

    expect(onSelectMode).toHaveBeenCalledWith("fleet");
    expect(screen.queryByRole("option", { name: "Недоступный" })).not.toBeInTheDocument();
  });
});

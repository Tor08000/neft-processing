import React from "react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { buildAdminPermissions } from "../admin/access";
import UsersPage from "./UsersPage";

const useAuthMock = vi.fn();
const useAdminMock = vi.fn();
const listUsersMock = vi.fn();
const updateUserMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../admin/AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

vi.mock("../api/adminUsers", () => ({
  listUsers: (...args: unknown[]) => listUsersMock(...args),
  updateUser: (...args: unknown[]) => updateUserMock(...args),
}));

vi.mock("../utils/correlationId", () => ({
  createCorrelationId: () => "corr-users-page-test",
}));

describe("UsersPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({
      accessToken: "admin-token",
      logout: vi.fn(),
    });
  });

  it("shows only admin-capable users from the broader auth-host registry", async () => {
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["PLATFORM_ADMIN"]),
        read_only: false,
      },
    });
    listUsersMock.mockResolvedValue([
      {
        id: "admin-1",
        email: "support@neft.test",
        full_name: "Support Admin",
        is_active: true,
        created_at: "2026-04-12T12:00:00Z",
        roles: ["NEFT_SUPPORT"],
      },
      {
        id: "client-1",
        email: "client@neft.test",
        full_name: "Client Manager",
        is_active: true,
        created_at: "2026-04-11T12:00:00Z",
        roles: ["CLIENT_MANAGER"],
      },
    ]);

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("support@neft.test")).toBeInTheDocument();
    expect(screen.queryByText("client@neft.test")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Добавить администратора" })).toHaveAttribute("href", "/admins/new");
    expect(screen.getAllByText("Support Admin").length).toBeGreaterThan(0);
  });

  it("hides management affordances when access contour is read-only", async () => {
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["PLATFORM_ADMIN"]),
        read_only: true,
      },
    });
    listUsersMock.mockResolvedValue([
      {
        id: "admin-1",
        email: "observer@neft.test",
        full_name: "Observer",
        is_active: true,
        created_at: "2026-04-12T12:00:00Z",
        roles: ["ANALYST"],
      },
    ]);

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("observer@neft.test")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Добавить администратора" })).not.toBeInTheDocument();
    expect(screen.queryByText("Редактировать")).not.toBeInTheDocument();
  });

  it("requires admin write metadata before toggling admin activity", async () => {
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["PLATFORM_ADMIN"]),
        read_only: false,
      },
    });
    listUsersMock.mockResolvedValue([
      {
        id: "admin-2",
        email: "ops@neft.test",
        full_name: "Ops Admin",
        is_active: true,
        created_at: "2026-04-12T12:00:00Z",
        roles: ["NEFT_OPS"],
      },
    ]);
    updateUserMock.mockResolvedValue({
      id: "admin-2",
      email: "ops@neft.test",
      full_name: "Ops Admin",
      is_active: false,
      created_at: "2026-04-12T12:00:00Z",
      roles: ["NEFT_OPS"],
    });

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Активен" }));
    expect(screen.getByRole("heading", { name: "Подтвердите отключение администратора" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Причина (обязательное поле)"), {
      target: { value: "Disable expired operator account" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));

    await waitFor(() =>
      expect(updateUserMock).toHaveBeenCalledWith("admin-token", "admin-2", {
        is_active: false,
        reason: "Disable expired operator account",
        correlation_id: "corr-users-page-test",
      }),
    );
  });

  it("shows a filtered-empty state with a reset path", async () => {
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["PLATFORM_ADMIN"]),
        read_only: false,
      },
    });
    listUsersMock.mockResolvedValue([
      {
        id: "admin-3",
        email: "finance@neft.test",
        full_name: "Finance Admin",
        is_active: true,
        created_at: "2026-04-12T12:00:00Z",
        roles: ["PLATFORM_ADMIN"],
      },
    ]);

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    );

    await screen.findByText("finance@neft.test");
    fireEvent.change(screen.getByLabelText("Поиск"), { target: { value: "missing-admin" } });

    expect(await screen.findByText("Администраторы не найдены")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сбросить фильтры" }));

    expect(await screen.findByText("finance@neft.test")).toBeInTheDocument();
  });
});

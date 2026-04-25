import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { buildAdminPermissions } from "../admin/access";
import CreateUserPage from "./CreateUserPage";
import EditUserPage from "./EditUserPage";

const useAuthMock = vi.fn();
const useAdminMock = vi.fn();
const listUsersMock = vi.fn();
const createUserMock = vi.fn();
const updateUserMock = vi.fn();
const fetchAuditFeedMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../admin/AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

vi.mock("../api/adminUsers", () => ({
  listUsers: (...args: unknown[]) => listUsersMock(...args),
  createUser: (...args: unknown[]) => createUserMock(...args),
  updateUser: (...args: unknown[]) => updateUserMock(...args),
}));

vi.mock("../api/audit", () => ({
  fetchAuditFeed: (...args: unknown[]) => fetchAuditFeedMock(...args),
}));

vi.mock("../utils/correlationId", () => ({
  createCorrelationId: () => "corr-admin-write-test",
}));

describe("Admin user write pages", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "admin-token" });
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["PLATFORM_ADMIN"]),
        read_only: false,
      },
    });
    fetchAuditFeedMock.mockResolvedValue({ items: [] });
  });

  const renderWithQuery = (node: React.ReactNode) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
  };

  it("sends reason and correlation metadata when creating an admin", async () => {
    createUserMock.mockResolvedValue({
      id: "admin-300",
      email: "new-admin@neft.test",
      full_name: "New Admin",
      is_active: true,
      created_at: "2026-04-13T10:00:00Z",
      roles: ["PLATFORM_ADMIN"],
    });

    const { container } = renderWithQuery(
      <MemoryRouter>
        <CreateUserPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByPlaceholderText("admin@neft.local"), { target: { value: "new-admin@neft.test" } });
    fireEvent.change(screen.getByPlaceholderText("Имя администратора"), { target: { value: "New Admin" } });
    const passwordInputs = container.querySelectorAll('input[type="password"]');
    fireEvent.change(passwordInputs[0] as HTMLInputElement, { target: { value: "secret123" } });
    fireEvent.change(passwordInputs[1] as HTMLInputElement, { target: { value: "secret123" } });
    fireEvent.submit(screen.getByRole("button", { name: "Создать" }));

    expect(screen.getByRole("heading", { name: "Подтвердите создание администратора" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Причина (обязательное поле)"), {
      target: { value: "Create new platform admin for rollout" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));

    await waitFor(() =>
      expect(createUserMock).toHaveBeenCalledWith("admin-token", {
        email: "new-admin@neft.test",
        password: "secret123",
        full_name: "New Admin",
        roles: ["ANALYST"],
        reason: "Create new platform admin for rollout",
        correlation_id: "corr-admin-write-test",
      }),
    );
  });

  it("keeps create-user validation local when passwords do not match", () => {
    const { container } = renderWithQuery(
      <MemoryRouter>
        <CreateUserPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByPlaceholderText("admin@neft.local"), { target: { value: "draft@neft.test" } });
    const passwordInputs = container.querySelectorAll('input[type="password"]');
    fireEvent.change(passwordInputs[0] as HTMLInputElement, { target: { value: "secret123" } });
    fireEvent.change(passwordInputs[1] as HTMLInputElement, { target: { value: "secret456" } });
    fireEvent.submit(screen.getByRole("button", { name: "Создать" }));

    expect(screen.getByText("Пароль и подтверждение не совпадают")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Подтвердите создание администратора" })).not.toBeInTheDocument();
    expect(createUserMock).not.toHaveBeenCalled();
  });

  it("sends reason and correlation metadata when changing admin roles", async () => {
    listUsersMock.mockResolvedValue([
      {
        id: "admin-400",
        email: "support@neft.test",
        full_name: "Support Admin",
        is_active: true,
        created_at: "2026-04-10T08:00:00Z",
        roles: ["ANALYST"],
      },
    ]);
    updateUserMock.mockResolvedValue({
      id: "admin-400",
      email: "support@neft.test",
      full_name: "Support Admin",
      is_active: true,
      created_at: "2026-04-10T08:00:00Z",
      roles: ["ANALYST", "NEFT_SUPPORT"],
    });

    renderWithQuery(
      <MemoryRouter initialEntries={["/admins/admin-400"]}>
        <Routes>
          <Route path="/admins/:id" element={<EditUserPage />} />
          <Route path="/admins" element={<div>Admins index</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await screen.findByText("support@neft.test");
    fireEvent.click(screen.getByLabelText(/Support Admin/));
    fireEvent.submit(screen.getByRole("button", { name: "Сохранить" }));

    expect(screen.getByRole("heading", { name: "Подтвердите изменение администратора" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Причина (обязательное поле)"), {
      target: { value: "Promote analyst to support admin" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));

    await waitFor(() =>
      expect(updateUserMock).toHaveBeenCalledWith("admin-token", "admin-400", {
        full_name: "Support Admin",
        is_active: true,
        roles: ["ANALYST", "NEFT_SUPPORT"],
        reason: "Promote analyst to support admin",
        correlation_id: "corr-admin-write-test",
      }),
    );
  });

  it("shows canonical audit deep links on the admin details page", async () => {
    listUsersMock.mockResolvedValue([
      {
        id: "admin-401",
        email: "audit@neft.test",
        full_name: "Audit Admin",
        is_active: true,
        created_at: "2026-04-10T08:00:00Z",
        roles: ["PLATFORM_ADMIN"],
      },
    ]);
    fetchAuditFeedMock.mockResolvedValue({
      items: [
        {
          id: "evt-1",
          title: "ADMIN_USER_UPDATED",
          entity_type: "admin_user",
          entity_id: "admin-401",
          correlation_id: "corr-admin-401",
          reason: "Rotate access",
          ts: "2026-04-13T11:00:00Z",
        },
      ],
    });

    renderWithQuery(
      <MemoryRouter initialEntries={["/admins/admin-401"]}>
        <Routes>
          <Route path="/admins/:id" element={<EditUserPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Audit activity")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open full audit" })).toHaveAttribute(
      "href",
      "/audit?entity_type=admin_user&entity_id=admin-401",
    );
    expect(screen.getByRole("link", { name: "Chain" })).toHaveAttribute("href", "/audit/corr-admin-401");
  });
});

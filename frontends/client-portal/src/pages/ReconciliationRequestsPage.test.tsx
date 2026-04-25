import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReconciliationRequestsPage } from "./ReconciliationRequestsPage";
import { AuthProvider } from "../auth/AuthContext";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), { status: 200 }))) as unknown as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ReconciliationRequestsPage", () => {
  it("shows empty state when no requests exist", async () => {
    render(
      <MemoryRouter initialEntries={["/finance/reconciliation"]}>
        <AuthProvider initialSession={session}>
          <Routes>
            <Route path="/finance/reconciliation" element={<ReconciliationRequestsPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Запросов пока нет" })).toBeInTheDocument();
  });

  it("renders an access-limited state instead of a disabled request form for non-finance roles", async () => {
    const limitedSession: AuthSession = {
      ...session,
      roles: ["CLIENT_DRIVER"],
    };

    render(
      <MemoryRouter initialEntries={["/finance/reconciliation"]}>
        <AuthProvider initialSession={limitedSession}>
          <Routes>
            <Route path="/finance/reconciliation" element={<ReconciliationRequestsPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Создание запроса недоступно" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отправить запрос" })).not.toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReconciliationRequestsPage } from "./ReconciliationRequestsPage";
import { AuthProvider } from "../auth/AuthContext";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
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
      <AuthProvider initialSession={session}>
        <MemoryRouter initialEntries={["/finance/reconciliation"]}>
          <Routes>
            <Route path="/finance/reconciliation" element={<ReconciliationRequestsPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(await screen.findByText("Запросов пока нет.")).toBeInTheDocument();
  });
});

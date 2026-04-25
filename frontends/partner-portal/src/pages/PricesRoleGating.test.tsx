import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import type { AuthSession } from "../api/types";
import i18n from "../i18n";
import { PriceVersionDetailsPage } from "./PriceVersionDetailsPage";

const session: AuthSession = {
  token: "token-1",
  email: "operator@demo.test",
  roles: ["PARTNER_OPERATOR"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const mockFetch = (url: string) => {
  if (url.includes("/partner/prices/versions/") && !url.endsWith("/versions")) {
    return new Response(
      JSON.stringify({
        id: "version-1",
        partner_id: "partner-1",
        station_scope: "all",
        status: "PUBLISHED",
        created_at: new Date().toISOString(),
        active: true,
        item_count: 10,
        error_count: 0,
      }),
      {
        status: 200,
        headers: { "content-type": "application/json" },
      },
    );
  }
  if (url.includes("/partner/prices/versions")) {
    return new Response(JSON.stringify({ items: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
  return new Response(JSON.stringify({ items: [] }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Prices role gating", () => {
  it("hides publish and rollback actions for non-owners", async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <AuthProvider initialSession={session}>
          <MemoryRouter initialEntries={["/prices/version-1"]}>
            <Routes>
              <Route path="/prices/:id" element={<PriceVersionDetailsPage />} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </I18nextProvider>,
    );

    expect(await screen.findByText("Статус")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Публиковать/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Rollback/i })).not.toBeInTheDocument();
  });
});

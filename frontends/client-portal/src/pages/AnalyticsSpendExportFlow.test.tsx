import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { I18nProvider } from "../i18n";
import type { AuthSession } from "../api/types";
import { AnalyticsSpendPage } from "./AnalyticsSpendPage";

const ownerSession: AuthSession = {
  token: "token-analytics",
  email: "owner@example.com",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const spendSummaryPayload = {
  currency: "RUB",
  total_spend: 1500,
  avg_daily_spend: 750,
  trend: [
    { date: "2024-03-01", value: 700 },
    { date: "2024-03-02", value: 800 },
  ],
  top_stations: [{ name: "Station A", amount: 1000 }],
  top_merchants: [{ name: "Merchant A", amount: 1000 }],
  top_cards: [{ name: "Card A", amount: 1000 }],
  top_drivers: [{ name: "Driver A", amount: 1000 }],
  product_breakdown: [{ product: "DIESEL", amount: 1500 }],
  export_available: false,
  export_dataset: "spend",
};

describe("AnalyticsSpendPage export flow", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("creates a client-facing export job and opens the download URL in a separate step", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      if (url.includes("/bi/spend/summary")) {
        return new Response(JSON.stringify(spendSummaryPayload), { status: 200 });
      }
      if (url.endsWith("/bi/exports") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "job-1",
            dataset: "spend",
            status: "DELIVERED",
            format: "CSV",
            created_at: "2026-03-29T10:00:00Z",
            ready: true,
            error_message: null,
          }),
          { status: 200 },
        );
      }
      if (url.includes("/bi/exports/job-1/download")) {
        return new Response(
          JSON.stringify({
            id: "job-1",
            status: "DELIVERED",
            url: "https://downloads.example.com/spend.csv",
            sha256: "abc123",
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({}), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter>
        <I18nProvider locale="ru">
          <AuthProvider initialSession={ownerSession}>
            <AnalyticsSpendPage />
          </AuthProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    const exportButton = await screen.findByRole("button", { name: /csv/i });
    expect(exportButton).toBeEnabled();

    await userEvent.click(exportButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/bi/exports"),
        expect.objectContaining({ method: "POST" }),
      );
    });
    await waitFor(() =>
      expect(openSpy).toHaveBeenCalledWith("https://downloads.example.com/spend.csv", "_blank", "noopener"),
    );
  });
});

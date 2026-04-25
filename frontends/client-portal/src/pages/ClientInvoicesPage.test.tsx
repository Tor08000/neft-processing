import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@example.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const invoicesTitle = "\u0418\u043d\u0432\u043e\u0439\u0441\u044b";
const periodFromLabel = "\u041f\u0435\u0440\u0438\u043e\u0434 \u0441";
const totalsCopy = "\u041f\u043e\u043a\u0430\u0437\u0430\u043d\u044b 0 \u0438\u0437 0";
const emptyInvoicesCopy = "\u0421\u0447\u0435\u0442\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b";
const invoiceTitle = "\u0421\u0447\u0451\u0442 #402";
const paymentsTitle = "\u041f\u043b\u0430\u0442\u0435\u0436\u0438";
const totalLabel = "\u0421\u0443\u043c\u043c\u0430";

const seedActiveJourneyDraft = () => {
  window.localStorage.setItem(
    "neft_client_journey_draft",
    JSON.stringify({
      selectedPlan: "CLIENT_BUSINESS",
      customerType: "LEGAL_ENTITY",
      profileCompleted: true,
      documentsByCode: { service_agreement: "reviewed", onboarding_ack: "reviewed" },
      documentsSigned: true,
      signAccepted: true,
      subscriptionState: "ACTIVE",
    }),
  );
};

const buildPortalPayload = () => ({
  user: { id: "u-1", email: "client@example.test" },
  org: { id: "org-1", name: "\u041e\u041e\u041e \u0422\u0435\u0441\u0442", org_type: "LEGAL", status: "ACTIVE" },
  org_status: "ACTIVE",
  org_roles: ["CLIENT_OWNER"],
  user_roles: ["CLIENT_OWNER"],
  roles: ["CLIENT_OWNER"],
  capabilities: ["CLIENT_BILLING", "CLIENT_DASHBOARD"],
  nav_sections: [],
  modules: { analytics: { enabled: true } },
  features: { onboarding_enabled: true, legal_gate_enabled: false },
  access_state: "ACTIVE",
});

describe("Client invoices", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
    seedActiveJourneyDraft();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("renders empty state when no invoices", async () => {
    const invoicesResponse = new Response(
      JSON.stringify({
        items: [],
        total: 0,
        limit: 25,
        offset: 0,
      }),
      { status: 200 },
    );

    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = input.toString();
      if (url.includes("/portal/me")) {
        return Promise.resolve(new Response(JSON.stringify(buildPortalPayload()), { status: 200 }));
      }
      if (url.includes("/client/invoices")) {
        return Promise.resolve(invoicesResponse.clone());
      }
      return Promise.resolve(new Response(JSON.stringify({ detail: "not found" }), { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/invoices"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: invoicesTitle })).toBeInTheDocument();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) => input.toString().includes("/client/invoices")),
      ).toBe(true),
    );
    expect(screen.getByLabelText(periodFromLabel)).toBeInTheDocument();
    expect(screen.getByText(totalsCopy)).toBeInTheDocument();
    expect(screen.getByText(emptyInvoicesCopy)).toBeInTheDocument();
  });

  it("opens invoice details", async () => {
    const detailResponse = new Response(
      JSON.stringify({
        id: 402,
        org_id: 1,
        period_start: "2024-03-01",
        period_end: "2024-03-31",
        currency: "RUB",
        amount_total: 1500,
        amount_paid: 1000,
        amount_refunded: 0,
        amount_due: 500,
        status: "PAID",
        due_at: "2024-04-10",
        download_url: "/api/core/client/invoices/402/download",
        payments: [
          {
            amount: 1000,
            status: "POSTED",
            provider: "bank",
            external_ref: "ext-1",
            created_at: "2024-03-06T10:00:00Z",
          },
        ],
        refunds: [],
      }),
      { status: 200 },
    );

    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = input.toString();
      if (url.includes("/portal/me")) {
        return Promise.resolve(new Response(JSON.stringify(buildPortalPayload()), { status: 200 }));
      }
      if (url.includes("/client/invoices/402")) {
        return Promise.resolve(detailResponse.clone());
      }
      return Promise.resolve(new Response(JSON.stringify({ detail: "not found" }), { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/invoices/402"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: invoiceTitle })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: paymentsTitle })).toBeInTheDocument();
    const totalStatLabel = screen.getAllByText(totalLabel).find((element) =>
      element.closest(".finance-overview__card"),
    );
    expect(totalStatLabel).toBeTruthy();
    const totalStat = totalStatLabel?.closest(".finance-overview__card");
    expect(totalStat).not.toBeNull();
    expect(within(totalStat as HTMLElement).getByText(/\u20bd/)).toBeInTheDocument();
    expect(totalStat).toHaveTextContent("1 500");
  });
});

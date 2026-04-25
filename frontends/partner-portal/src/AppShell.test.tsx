import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { AuthSession, PortalMeResponse } from "./api/types";
import i18n from "./i18n";

const session: AuthSession = {
  token: "token-1",
  email: "partner@neft.local",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const financePortal: PortalMeResponse = {
  user: {
    id: "user-1",
    email: session.email,
    subject_type: session.subjectType,
  },
  org_roles: ["PARTNER"],
  user_roles: ["PARTNER_ACCOUNTANT"],
  capabilities: ["PARTNER_FINANCE_VIEW", "PARTNER_PAYOUT_REQUEST", "PARTNER_SETTLEMENTS", "PARTNER_DOCUMENTS_LIST"],
  access_state: "ACTIVE",
  gating: {
    onboarding_enabled: false,
    legal_gate_enabled: false,
  },
  partner: {
    kind: "FINANCE_PARTNER",
    partner_role: "FINANCE_MANAGER",
    partner_roles: ["FINANCE_MANAGER"],
    default_route: "/finance",
    workspaces: [
      { code: "finance", label: "Finance", default_route: "/finance" },
      { code: "support", label: "Support", default_route: "/support/requests" },
      { code: "profile", label: "Profile", default_route: "/partner/profile" },
    ],
    legal_state: { status: "VERIFIED" },
  },
};

const marketplacePortal: PortalMeResponse = {
  user: {
    id: "user-1",
    email: session.email,
    subject_type: session.subjectType,
  },
  org_roles: ["PARTNER"],
  user_roles: ["PARTNER_OWNER"],
  capabilities: ["PARTNER_CATALOG", "PARTNER_PRICING", "PARTNER_ORDERS"],
  access_state: "ACTIVE",
  gating: {
    onboarding_enabled: false,
    legal_gate_enabled: false,
  },
  partner: {
    kind: "MARKETPLACE_PARTNER",
    partner_role: "OWNER",
    partner_roles: ["OWNER"],
    default_route: "/dashboard",
    workspaces: [
      { code: "marketplace", label: "Marketplace", default_route: "/products" },
      { code: "support", label: "Support", default_route: "/support/requests" },
      { code: "profile", label: "Profile", default_route: "/partner/profile" },
    ],
  },
};

const jsonResponse = (body: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );

let portalPayload: PortalMeResponse = financePortal;

beforeEach(() => {
  portalPayload = financePortal;
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof Request ? input.url : input.toString();
      if (url.includes("/partner/auth/verify")) {
        return jsonResponse({ ok: true });
      }
      if (url.includes("/portal/me")) {
        return jsonResponse(portalPayload);
      }
      if (url.includes("/partner/balance")) {
        return jsonResponse({
          partner_org_id: "partner-1",
          currency: "RUB",
          balance_available: 12000,
          balance_pending: 500,
          balance_blocked: 0,
        });
      }
      if (url.includes("/partner/ledger")) {
        return jsonResponse({ items: [], totals: { in: 12000, out: 0, net: 12000 }, next_cursor: null });
      }
      if (url.includes("/partner/finance/dashboard")) {
        return jsonResponse({
          active_contracts: 2,
          current_settlement_period: "2024-03-01 — 2024-03-31",
          upcoming_payout: 120000,
          sla: { status: "OK", violations: 0 },
        });
      }
      if (url.includes("/partner/payouts/preview")) {
        return jsonResponse({ legal_status: "VERIFIED", warnings: [] });
      }
      if (url.includes("/partner/payouts") && !url.includes("/request")) {
        return jsonResponse({ items: [] });
      }
      if (url.includes("/partner/exports/jobs")) {
        return jsonResponse({ items: [] });
      }
      if (url.includes("/partner/catalog")) {
        return jsonResponse({ items: [] });
      }
      return jsonResponse({ items: [] });
    }) as unknown as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Partner portal shell", () => {
  it("shows finance section only for finance partner", async () => {
    portalPayload = financePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/"]}>
          <App initialSession={session} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("heading", { name: /Баланс/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Дашборд$/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Финансы$/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Выплаты$/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Settlement$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^РљРѕРЅС‚СЂР°РєС‚С‹$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Товары$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Услуги$/ })).not.toBeInTheDocument();
  });

  it("shows marketplace section and hides finance when finance capability is absent", async () => {
    portalPayload = marketplacePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <App initialSession={session} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("heading", { name: /Следующие действия по разделам/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Дашборд$/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Товары$/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Заказы$/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Финансы$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Settlement$/ })).not.toBeInTheDocument();
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession, PortalMeResponse } from "../api/types";
import i18n from "../i18n";

const session: AuthSession = {
  token: "token-1",
  email: "owner@neft.local",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const portalMe: PortalMeResponse = {
  user: {
    id: "user-1",
    email: session.email,
    subject_type: session.subjectType,
  },
  org_roles: ["PARTNER"],
  user_roles: ["PARTNER_OWNER"],
  capabilities: ["PARTNER_ORDERS"],
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

const mockFetch = (url: string) => {
  if (url.includes("/partner/auth/verify")) {
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
  if (url.includes("/portal/me")) {
    return new Response(JSON.stringify(portalMe), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
  if (url.includes("/v1/marketplace/partner/orders")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "order-1",
            client_id: "client-1",
            partner_id: "partner-1",
            status: "CREATED",
            payment_status: "PAID",
            total_amount: 1000,
            lines: [
              { offer_id: "offer-1", title_snapshot: "РњРѕР№РєР°", qty: 1, unit_price: 1000, line_amount: 1000 },
            ],
            sla_response_remaining_seconds: 600,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        page: 1,
        pageSize: 20,
        total: 1,
      }),
      {
        status: 200,
        headers: { "content-type": "application/json" },
      },
    );
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

describe("OrdersPage", () => {
  it("renders orders list with SLA timer", async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/orders"]}>
          <App initialSession={session} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByText("order-1")).toBeInTheDocument();
    expect(screen.getByText("client-1")).toBeInTheDocument();
    expect(screen.getByText("РњРѕР№РєР°")).toBeInTheDocument();
    expect(screen.getByText("00:10:00")).toBeInTheDocument();
    const summary = document.querySelector(".table-footer__content > .muted");
    expect(summary?.textContent?.trim()).toBe(
      i18n.t("marketplace.ordersPage.pagination.shown", { visible: 1, total: 1 }),
    );
  });

  it("shows filtered empty state for narrowed order search", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof Request ? input.url : input.toString();
        if (url.includes("/partner/auth/verify")) {
          return Promise.resolve(mockFetch(url));
        }
        if (url.includes("/portal/me")) {
          return Promise.resolve(mockFetch(url));
        }
        if (url.includes("/v1/marketplace/partner/orders")) {
          const empty = url.includes("status=PAID");
          return Promise.resolve(
            new Response(
              JSON.stringify({
                items: empty
                  ? []
                  : [
                      {
                        id: "order-1",
                        client_id: "client-1",
                        partner_id: "partner-1",
                        status: "CREATED",
                        payment_status: "PAID",
                        total_amount: 1000,
                        lines: [
                          { offer_id: "offer-1", title_snapshot: "РњРѕР№РєР°", qty: 1, unit_price: 1000, line_amount: 1000 },
                        ],
                        sla_response_remaining_seconds: 600,
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString(),
                      },
                    ],
                page: 1,
                pageSize: 20,
                total: empty ? 0 : 1,
              }),
              {
                status: 200,
                headers: { "content-type": "application/json" },
              },
            ),
          );
        }
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }));
      }) as unknown as typeof fetch,
    );

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/orders"]}>
          <App initialSession={session} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByText("order-1")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/РЎС‚Р°С‚СѓСЃ|marketplace\.ordersPage\.filters\.status/), { target: { value: "PAID" } });

    await waitFor(() => {
      expect(screen.queryByText("order-1")).not.toBeInTheDocument();
    });
  });
});

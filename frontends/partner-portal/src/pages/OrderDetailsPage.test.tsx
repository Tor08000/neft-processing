import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession, PortalMeResponse } from "../api/types";
import i18n from "../i18n";

const ownerSession: AuthSession = {
  token: "token-1",
  email: "owner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const portalMe: PortalMeResponse = {
  user: {
    id: "user-1",
    email: ownerSession.email,
    subject_type: ownerSession.subjectType,
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

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });

const orderPayloadCreated = {
  id: "order-1",
  client_id: "client-1",
  partner_id: "partner-1",
  status: "PAID",
  payment_status: "PAID",
  total_amount: 1000,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  lines: [{ offer_id: "offer-1", title_snapshot: "РњРѕР№РєР°", qty: 1, unit_price: 1000, line_amount: 1000 }],
};

const buildMockFetch = (
  orderPayload: Record<string, unknown>,
  settlementPayload: Record<string, unknown> = {
    gross_amount: 1000,
    currency: "RUB",
    platform_fee: {
      amount: 150,
      explain: "Platform fee",
    },
    penalties: [],
    partner_net: 850,
    snapshot: {
      finalized_at: new Date().toISOString(),
      hash: "snapshot-hash-1",
    },
  },
) => (url: string) => {
  if (url.includes("/partner/auth/verify")) {
    return jsonResponse({ ok: true });
  }
  if (url.includes("/portal/me")) {
    return jsonResponse(portalMe);
  }
  if (url.includes("/v1/marketplace/partner/orders/order-1/events")) {
    return jsonResponse([
      {
        id: "event-1",
        event_type: "CREATED",
        created_at: new Date().toISOString(),
      },
    ]);
  }
  if (url.includes("/v1/marketplace/partner/orders/order-1/incidents")) {
    return jsonResponse({
      items: [
        {
          id: "case-order-1",
          title: "Client reported delivery issue",
          status: "TRIAGE",
          queue: "SUPPORT",
          case_source_ref_type: "MARKETPLACE_ORDER",
          case_source_ref_id: "order-1",
          updated_at: new Date().toISOString(),
        },
      ],
    });
  }
  if (url.includes("/v1/marketplace/partner/orders/order-1/sla")) {
    return jsonResponse({
      obligations: [
        {
          metric: "response_time",
          remainingSeconds: 600,
          totalSeconds: 3600,
          status: "OK",
        },
      ],
    });
  }
  if (url.includes("/v1/marketplace/partner/orders/order-1/settlement")) {
    return jsonResponse(settlementPayload);
  }
  if (url.includes("/v1/marketplace/partner/orders/order-1")) {
    return jsonResponse(orderPayload);
  }
  return jsonResponse({ items: [] });
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo) => Promise.resolve(buildMockFetch(orderPayloadCreated)(String(input)))) as unknown as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("OrderDetailsPage", () => {
  it("shows confirm and decline on PAID", async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/orders/order-1"]}>
          <App initialSession={ownerSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(
      await screen.findByRole("heading", {
        name: i18n.t("marketplace.orderDetails.title", { id: "order-1" }),
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: i18n.t("marketplace.orderDetails.actions.confirm") })).toBeEnabled();
    expect(screen.getByRole("button", { name: i18n.t("marketplace.orderDetails.actions.decline") })).toBeEnabled();
  });

  it("validates decline modal", async () => {
    const user = userEvent.setup();

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/orders/order-1"]}>
          <App initialSession={ownerSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    await user.click(await screen.findByRole("button", { name: i18n.t("marketplace.orderDetails.actions.decline") }));

    const dialog = await screen.findByRole("dialog");
    const confirmButton = within(dialog).getByRole("button", {
      name: i18n.t("marketplace.orderDetails.actions.confirm"),
    });
    expect(confirmButton).toBeDisabled();

    await user.type(
      within(dialog).getByLabelText(i18n.t("marketplace.orderDetails.modals.decline.reason")),
      "OUT_OF_STOCK",
    );
    await user.type(
      within(dialog).getByLabelText(i18n.t("marketplace.orderDetails.modals.decline.comment")),
      "РќРµС‚ РЅР° СЃРєР»Р°РґРµ",
    );
    expect(confirmButton).toBeEnabled();
  });

  it("shows honest frozen payout contour instead of settlement deep link", async () => {
    const user = userEvent.setup();

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/orders/order-1"]}>
          <App initialSession={ownerSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    await screen.findByRole("heading", {
      name: i18n.t("marketplace.orderDetails.title", { id: "order-1" }),
    });
    await user.click(screen.getByRole("button", { name: i18n.t("marketplace.orderDetails.tabs.payouts") }));

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: i18n.t("marketplace.orderDetails.payouts.frozenTitle"),
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: i18n.t("marketplace.orderDetails.payouts.openFinance"),
      }),
    ).toHaveAttribute("href", "/finance");
    expect(
      screen.getByRole("link", {
        name: i18n.t("marketplace.orderDetails.payouts.openSupport"),
      }),
    ).toHaveAttribute("href", "/support/requests");
  });

  it("renders order-linked incidents through the canonical case trail", async () => {
    const user = userEvent.setup();

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/orders/order-1"]}>
          <App initialSession={ownerSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    await screen.findByRole("heading", {
      name: i18n.t("marketplace.orderDetails.title", { id: "order-1" }),
    });
    await user.click(screen.getByRole("button", { name: i18n.t("marketplace.orderDetails.tabs.incidents") }));

    expect(await screen.findByText("Client reported delivery issue")).toBeInTheDocument();
    expect(screen.getByText("MARKETPLACE_ORDER / order-1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("common.open") })).toHaveAttribute("href", "/cases/case-order-1");
  });

  it("renders honest settlement empty states when penalties and snapshot are missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) =>
        Promise.resolve(
          buildMockFetch(
            {
              ...orderPayloadCreated,
              proofs: [],
            },
            {
              gross_amount: 1000,
              currency: "RUB",
              platform_fee: {
                amount: 150,
                explain: "Platform fee",
              },
              penalties: [],
              partner_net: 850,
              snapshot: null,
            },
          )(String(input)),
        )) as unknown as typeof fetch,
    );

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/orders/order-1"]}>
          <App initialSession={ownerSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    await screen.findByRole("heading", {
      name: i18n.t("marketplace.orderDetails.title", { id: "order-1" }),
    });
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: i18n.t("marketplace.orderDetails.settlement.noPenaltiesTitle"),
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: i18n.t("marketplace.orderDetails.settlement.snapshot.pendingTitle"),
      }),
    ).toBeInTheDocument();
  });

  it("shows settlement readiness state without handled ApiError noise", async () => {
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/v1/marketplace/partner/orders/order-1/settlement")) {
        return Promise.resolve(
          jsonResponse(
            {
              error: "SETTLEMENT_NOT_FINALIZED",
              detail: "Settlement snapshot is not finalized yet",
            },
            409,
          ),
        );
      }
      return Promise.resolve(buildMockFetch(orderPayloadCreated)(url));
    });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/orders/order-1"]}>
          <App initialSession={ownerSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    await screen.findByRole("heading", {
      name: i18n.t("marketplace.orderDetails.title", { id: "order-1" }),
    });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call: unknown[]) => {
          const [input] = call as [RequestInfo | URL];
          return String(input).includes("/v1/marketplace/partner/orders/order-1/settlement");
        }),
      ).toBe(true),
    );
    await waitFor(() => expect(consoleErrorSpy).not.toHaveBeenCalled());
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: i18n.t("marketplace.orderDetails.settlement.pendingTitle"),
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(i18n.t("marketplace.orderDetails.settlement.pendingDescription"))).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: i18n.t("marketplace.orderDetails.settlement.pendingActions.openFinance"),
      }),
    ).toHaveAttribute("href", "/finance");
    expect(
      screen.getByRole("link", {
        name: i18n.t("marketplace.orderDetails.settlement.pendingActions.openSupport"),
      }),
    ).toHaveAttribute("href", "/support/requests");
  });
});

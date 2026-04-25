import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession, PortalMeResponse } from "../api/types";
import i18n from "../i18n";

const financeSession: AuthSession = {
  token: "token-finance",
  email: "finance@neft.local",
  roles: ["PARTNER_ACCOUNTANT"],
  subjectType: "PARTNER",
  partnerId: "partner-finance-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const serviceSession: AuthSession = {
  token: "token-service",
  email: "service@neft.local",
  roles: ["PARTNER_SERVICE_MANAGER"],
  subjectType: "PARTNER",
  partnerId: "partner-service-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const financePortal: PortalMeResponse = {
  user: {
    id: "user-finance-1",
    email: financeSession.email,
    subject_type: financeSession.subjectType,
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

const financeAnalystPortal: PortalMeResponse = {
  ...financePortal,
  user: {
    ...financePortal.user,
    id: "user-finance-analyst-1",
    email: "analyst@neft.local",
  },
  user_roles: ["PARTNER_ANALYST"],
  partner: {
    ...financePortal.partner,
    partner_role: "ANALYST",
    partner_roles: ["ANALYST"],
  },
};

const settlementOnlyPortal: PortalMeResponse = {
  ...financePortal,
  user: {
    ...financePortal.user,
    id: "user-settlement-only-1",
    email: "settlement-only@neft.local",
  },
  user_roles: ["PARTNER_SETTLEMENTS_ANALYST"],
  capabilities: ["PARTNER_SETTLEMENTS"],
  partner: {
    ...financePortal.partner,
    partner_role: "SETTLEMENTS_ANALYST",
    partner_roles: ["SETTLEMENTS_ANALYST"],
  },
};

const servicePortal: PortalMeResponse = {
  user: {
    id: "user-service-1",
    email: serviceSession.email,
    subject_type: serviceSession.subjectType,
  },
  org_roles: ["PARTNER"],
  user_roles: ["PARTNER_SERVICE_MANAGER"],
  capabilities: ["PARTNER_CORE"],
  access_state: "ACTIVE",
  gating: {
    onboarding_enabled: false,
    legal_gate_enabled: false,
  },
  partner: {
    kind: "SERVICE_PARTNER",
    partner_role: "MANAGER",
    partner_roles: ["MANAGER"],
    default_route: "/services",
    workspaces: [
      { code: "services", label: "Services", default_route: "/services" },
      { code: "support", label: "Support", default_route: "/support/requests" },
      { code: "profile", label: "Profile", default_route: "/partner/profile" },
    ],
  },
};

const jsonResponse = (body: unknown, status = 200, headers?: Record<string, string>) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...(headers ?? {}) },
  });

let portalPayload: PortalMeResponse = financePortal;

const mockFetch = (url: string) => {
  if (url.includes("/partner/auth/verify")) {
    return jsonResponse({ ok: true });
  }
  if (url.includes("/portal/me")) {
    return jsonResponse(portalPayload);
  }
  if (url.includes("/partner/finance/dashboard")) {
    return jsonResponse({
      active_contracts: 4,
      current_settlement_period: "2026-04",
      upcoming_payout: 183000,
      sla_score: 97.4,
      sla: { status: "GREEN", violations: 0 },
    });
  }
  if (url.includes("/partner/balance")) {
    return jsonResponse({
      partner_org_id: "partner-finance-1",
      currency: "RUB",
      balance_available: 12000,
      balance_pending: 500,
      balance_blocked: 0,
    });
  }
  if (url.includes("/partner/ledger")) {
    return jsonResponse({
      items: [],
      totals: { in: 12000, out: 500, net: 11500 },
      cursor: null,
      next_cursor: null,
      total: 0,
    });
  }
  if (url.includes("/partner/exports/jobs")) {
    return jsonResponse({ items: [] });
  }
  if (url.includes("/partner/contracts/contract-1")) {
    return jsonResponse({
      id: "contract-1",
      contract_number: "MP-2026-001",
      contract_type: "marketplace",
      party_role: "party_a",
      counterparty_type: "CLIENT",
      counterparty_id: "client-1",
      currency: "RUB",
      status: "ACTIVE",
      effective_from: "2026-04-01T00:00:00Z",
      effective_to: null,
      created_at: "2026-04-01T00:00:00Z",
    });
  }
  if (url.includes("/partner/contracts")) {
    return jsonResponse({
      items: [
        {
          id: "contract-1",
          contract_number: "MP-2026-001",
          contract_type: "marketplace",
          party_role: "party_a",
          counterparty_type: "CLIENT",
          counterparty_id: "client-1",
          currency: "RUB",
          status: "ACTIVE",
          effective_from: "2026-04-01T00:00:00Z",
          effective_to: null,
          created_at: "2026-04-01T00:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
  }
  if (url.includes("/partner/settlements/set-1")) {
    return jsonResponse({
      id: "set-1",
      partner_id: "partner-finance-1",
      currency: "RUB",
      period_start: "2026-04-01T00:00:00Z",
      period_end: "2026-04-30T23:59:59Z",
      status: "APPROVED",
      total_gross: 100000,
      total_fees: 7000,
      total_refunds: 0,
      net_amount: 93000,
      period_hash: "hash-set-1",
      snapshot_payload: {},
      created_at: "2026-04-30T23:59:59Z",
      approved_at: "2026-05-01T10:00:00Z",
      paid_at: null,
      marketplace_snapshots_count: 1,
      items: [
        {
          id: "settlement-item-1",
          source_type: "marketplace_order",
          source_id: "order-1",
          amount: 93000,
          direction: "credit",
          created_at: "2026-04-30T23:59:59Z",
        },
      ],
      marketplace_snapshots: [
        {
          id: "snapshot-1",
          order_id: "order-1",
          gross_amount: 100000,
          platform_fee: 7000,
          penalties: 0,
          partner_net: 93000,
          currency: "RUB",
          finalized_at: "2026-04-30T23:59:59Z",
          hash: "snapshot-hash-1",
        },
      ],
    });
  }
  if (url.includes("/partner/settlements")) {
    return jsonResponse({
      items: [
        {
          id: "set-1",
          partner_id: "partner-finance-1",
          currency: "RUB",
          period_start: "2026-04-01T00:00:00Z",
          period_end: "2026-04-30T23:59:59Z",
          status: "APPROVED",
          total_gross: 100000,
          total_fees: 7000,
          total_refunds: 0,
          net_amount: 93000,
          period_hash: "hash-set-1",
          snapshot_payload: {},
          created_at: "2026-04-30T23:59:59Z",
          approved_at: "2026-05-01T10:00:00Z",
          paid_at: null,
          marketplace_snapshots_count: 1,
          items: null,
          marketplace_snapshots: null,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
  }
  if (url.includes("/partner/payouts/preview")) {
    return jsonResponse({ legal_status: "VERIFIED", warnings: [] });
  }
  if (url.includes("/partner/payouts") && !url.includes("/request")) {
    return jsonResponse({ items: [] });
  }
  if (url.includes("/cases/request-1")) {
    return jsonResponse({
      case: {
        id: "request-1",
        tenant_id: 1,
        kind: "dispute",
        queue: "support_finance",
        entity_type: "SETTLEMENT",
        entity_id: "set-1",
        title: "Settlement discrepancy",
        description: "Need clarification on settlement breakdown",
        status: "WAITING",
        priority: "MEDIUM",
        partner_id: financeSession.partnerId,
        case_source_ref_type: "SUPPORT_REQUEST",
        case_source_ref_id: "support-request-1",
        first_response_due_at: "2099-04-19T12:00:00Z",
        resolve_due_at: "2099-04-19T14:00:00Z",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      timeline: [{ status: "WAITING", occurred_at: new Date().toISOString() }],
    });
  }
  if (url.includes("/partner/catalog")) {
    return jsonResponse({
      items: [
        {
          id: "catalog-1",
          kind: "SERVICE",
          title: "Мойка",
          description: "Полный комплекс",
          category: "Автомойка",
          baseUom: "услуга",
          status: "ACTIVE",
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          activeOffersCount: 1,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });
  }
  return jsonResponse({ items: [] });
};

beforeEach(() => {
  portalPayload = financePortal;
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        mockFetch(typeof input === "string" ? input : input instanceof Request ? input.url : input.toString()),
      )) as unknown as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Partner pages", () => {
  it("renders dashboard as an action-oriented console for finance partners", async () => {
    portalPayload = financePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Кабинет партнёра" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Фокус на сейчас" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Операционный обзор" })).toBeInTheDocument();
    expect(await screen.findByText("Contracts and settlements")).toBeInTheDocument();
    const financeLinks = screen.getAllByRole("link", { name: "Открыть финансы" });
    expect(financeLinks.length).toBeGreaterThan(0);
    financeLinks.forEach((link) => expect(link).toHaveAttribute("href", "/finance"));
    const fetchCalls = (fetch as unknown as { mock: { calls: Array<[RequestInfo | URL]> } }).mock.calls;
    const dashboardCalls = fetchCalls.filter(([input]) => String(input).includes("/partner/finance/dashboard"));
    expect(dashboardCalls).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Contracts" })).toHaveAttribute("href", "/contracts");
    expect(screen.getByRole("link", { name: "Settlements" })).toHaveAttribute("href", "/settlements");
  });

  it("renders mounted settlement route for finance partner", async () => {
    portalPayload = financePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/settlements"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Settlements" })).toBeInTheDocument();
    expect(screen.getByText("Read-only settlement periods from the finance owner.")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Details" })).toHaveAttribute("href", "/settlements/set-1");
  });

  it("renders mounted settlement detail from owner data", async () => {
    portalPayload = financePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/settlements/set-1"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Settlement details" })).toBeInTheDocument();
    expect(await screen.findByText("hash-set-1")).toBeInTheDocument();
    expect(await screen.findByText("snapshot-hash-1")).toBeInTheDocument();
    const ownerFetchUrls = (fetch as unknown as { mock: { calls: Array<[RequestInfo | URL]> } }).mock.calls.map(([input]) =>
      String(input),
    );
    expect(ownerFetchUrls.some((url) => url.includes("/partner/settlements/set-1"))).toBe(true);
  });

  it("renders mounted contracts route for finance partner", async () => {
    portalPayload = financePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/contracts"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Contracts" })).toBeInTheDocument();
    expect(await screen.findByText("MP-2026-001")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Details" })).toHaveAttribute("href", "/contracts/contract-1");
  });

  it("renders mounted contract detail from owner data", async () => {
    portalPayload = financePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/contracts/contract-1"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Contract details" })).toBeInTheDocument();
    expect(await screen.findByText("MP-2026-001")).toBeInTheDocument();
    expect(await screen.findByText("client-1")).toBeInTheDocument();
  });

  it("requires finance-view capability for mounted settlement routes", async () => {
    portalPayload = settlementOnlyPortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/settlements"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Функция недоступна" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Settlements" })).not.toBeInTheDocument();
  });

  it("redirects service partners away from finance deep links", async () => {
    portalPayload = servicePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/contracts"]}>
          <App initialSession={serviceSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    const currentLink = await screen.findByRole("link", { current: "page" });
    expect(currentLink).toHaveAttribute("href", "/services");
    expect(screen.queryByRole("heading", { name: "Contracts" })).not.toBeInTheDocument();
  });

  it("redirects service partners away from marketplace-only routes", async () => {
    portalPayload = servicePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/products"]}>
          <App initialSession={serviceSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    const currentLink = await screen.findByRole("link", { current: "page" });
    expect(currentLink).toHaveAttribute("href", "/services");
    expect(screen.queryByRole("heading", { name: "Каталог маркетплейса" })).not.toBeInTheDocument();
  });

  it("renders support detail on the canonical case route without leaving the mounted support contour", async () => {
    portalPayload = financePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/cases/request-1"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("link", { name: i18n.t("common.back") })).toHaveAttribute("href", "/support/requests");
    expect(screen.getByRole("link", { name: i18n.t("nav.supportRequests") })).toHaveAttribute("href", "/support/requests");
    expect(screen.getByRole("link", { name: i18n.t("nav.supportRequests") })).toHaveAttribute("aria-current", "page");
    expect(document.querySelector('a[href="/cases"]')).toBeNull();
    const link = await screen.findByRole("link", { name: "SETTLEMENT #set-1" });
    expect(link).toHaveAttribute("href", "/finance");
    expect(screen.getByText("support_finance")).toBeInTheDocument();
    expect(screen.getByText("SUPPORT_REQUEST / support-request-1")).toBeInTheDocument();
  });

  it("opens support list rows through the canonical case route", async () => {
    portalPayload = financePortal;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof Request ? input.url : input.toString();
        if (url.includes("/cases?")) {
          return Promise.resolve(
            jsonResponse({
              items: [
                {
                  id: "request-list-1",
                  tenant_id: 1,
                  kind: "support",
                  queue: "support_finance",
                  entity_type: "INTEGRATION",
                  entity_id: "sync-1",
                  title: "Integration sync issue",
                  description: "Delivery lag",
                  status: "WAITING",
                  priority: "MEDIUM",
                  partner_id: financeSession.partnerId,
                  case_source_ref_type: "SUPPORT_REQUEST",
                  case_source_ref_id: "support-request-list-1",
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ],
              total: 1,
              limit: 50,
              next_cursor: null,
            }),
          );
        }
        return Promise.resolve(mockFetch(url));
      }) as unknown as typeof fetch,
    );

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/support/requests"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("link", { name: "Integration sync issue" })).toHaveAttribute(
      "href",
      "/cases/request-list-1",
    );
    expect(screen.getByRole("link", { name: i18n.t("common.open") })).toHaveAttribute("href", "/cases/request-list-1");
  });

  it("renders canonical support list retry state with correlation id", async () => {
    portalPayload = financePortal;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof Request ? input.url : input.toString();
        if (url.includes("/cases?")) {
          return Promise.resolve(
            jsonResponse(
              { message: "Support contour unavailable" },
              503,
              { "x-correlation-id": "corr-support-list" },
            ),
          );
        }
        return Promise.resolve(mockFetch(url));
      }) as unknown as typeof fetch,
    );

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/support/requests"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByText(i18n.t("errors.correlationId", { id: "corr-support-list" }))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: i18n.t("actions.retry") })).toBeInTheDocument();
  });

  it("retries support request details and keeps an honest empty timeline state", async () => {
    portalPayload = financePortal;
    const user = userEvent.setup();
    let detailAttempts = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof Request ? input.url : input.toString();
        if (url.includes("/cases/request-retry")) {
          detailAttempts += 1;
          if (detailAttempts === 1) {
            return Promise.reject(new Error("temporary support failure"));
          }
          return Promise.resolve(
            jsonResponse({
              case: {
                id: "request-retry",
                tenant_id: 1,
                kind: "dispute",
                queue: "support_finance",
                entity_type: "SETTLEMENT",
                entity_id: "set-2",
                title: "Retry settlement case",
                description: "Need one more sync",
                status: "WAITING",
                priority: "MEDIUM",
                partner_id: financeSession.partnerId,
                case_source_ref_type: "SUPPORT_REQUEST",
                case_source_ref_id: "support-request-2",
                first_response_due_at: "2099-04-19T12:00:00Z",
                resolve_due_at: "2099-04-19T14:00:00Z",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
              timeline: [],
            }),
          );
        }
        return Promise.resolve(mockFetch(url));
      }) as unknown as typeof fetch,
    );

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/support/requests/request-retry"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Не удалось загрузить обращение" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Повторить" }));

    expect(await screen.findByText("Retry settlement case")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Хронология пока пуста" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "SETTLEMENT #set-2" })).toHaveAttribute("href", "/finance");
    expect(screen.getByText("support_finance")).toBeInTheDocument();
    expect(screen.getByText("SUPPORT_REQUEST / support-request-2")).toBeInTheDocument();
  });

  it("renders not-found state for missing support detail", async () => {
    portalPayload = financePortal;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof Request ? input.url : input.toString();
        if (url.includes("/cases/request-missing")) {
          return Promise.resolve(jsonResponse({ detail: "missing" }, 404, { "x-correlation-id": "corr-404" }));
        }
        return Promise.resolve(mockFetch(url));
      }) as unknown as typeof fetch,
    );

    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/support/requests/request-missing"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByText(i18n.t("supportRequests.detailNotFoundDescription"))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: i18n.t("common.back") })).toHaveAttribute("href", "/support/requests");
  });

  it("keeps finance analyst in read-only payout mode", async () => {
    portalPayload = financeAnalystPortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/payouts"]}>
          <App initialSession={{ ...financeSession, email: "analyst@neft.local", roles: ["PARTNER_ANALYST"] }} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByText("Режим только для чтения")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Запросить" })).toBeDisabled();
    expect(screen.getByRole("heading", { name: "История выплат пока пуста" })).toBeInTheDocument();
  });

  it("renders finance section with honest empty ledger and export states", async () => {
    portalPayload = financePortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/finance"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Баланс" })).toBeInTheDocument();
    expect(await screen.findByText("Начисления и списания появятся после завершения заказов.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Экспортов пока нет" })).toBeInTheDocument();
  });
});

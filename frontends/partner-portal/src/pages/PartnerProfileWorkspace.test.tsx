import { render, screen } from "@testing-library/react";
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
  email: "owner@neft.local",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-service-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const financeManagerPortal: PortalMeResponse = {
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
  ...financeManagerPortal,
  user: {
    ...financeManagerPortal.user,
    id: "user-finance-analyst-1",
    email: "analyst@neft.local",
  },
  user_roles: ["PARTNER_ANALYST"],
  partner: {
    ...financeManagerPortal.partner,
    partner_role: "ANALYST",
    partner_roles: ["ANALYST"],
  },
};

const serviceOwnerPortal: PortalMeResponse = {
  user: {
    id: "user-service-1",
    email: serviceSession.email,
    subject_type: serviceSession.subjectType,
  },
  org_roles: ["PARTNER"],
  user_roles: ["PARTNER_OWNER"],
  capabilities: ["PARTNER_CORE"],
  access_state: "ACTIVE",
  gating: {
    onboarding_enabled: false,
    legal_gate_enabled: false,
  },
  partner: {
    kind: "SERVICE_PARTNER",
    partner_role: "OWNER",
    partner_roles: ["OWNER"],
    default_route: "/services",
    workspaces: [
      { code: "services", label: "Services", default_route: "/services" },
      { code: "support", label: "Support", default_route: "/support/requests" },
      { code: "profile", label: "Profile", default_route: "/partner/profile" },
    ],
    legal_state: { status: "PENDING" },
  },
};

const profilePayload = {
  partner: {
    id: "partner-1",
    code: "partner-001",
    legal_name: "ООО Партнёр",
    brand_name: "NEFT Partner",
    partner_type: "OTHER",
    inn: "7701000000",
    ogrn: "1027700000000",
    status: "ACTIVE",
    contacts: {
      email: "finance@partner.ru",
      phone: "+7 900 000 00 00",
    },
  },
  my_roles: ["PARTNER_OWNER"],
};

const usersPayload = [
  {
    user_id: "owner@partner.ru",
    roles: ["PARTNER_OWNER"],
    created_at: "2026-04-13T09:00:00Z",
  },
  {
    user_id: "manager@partner.ru",
    roles: ["PARTNER_MANAGER"],
    created_at: "2026-04-13T10:00:00Z",
  },
];

const termsPayload = {
  id: "terms-1",
  partner_id: "partner-1",
  version: 3,
  status: "ACTIVE",
  created_at: "2026-04-10T09:00:00Z",
  updated_at: "2026-04-12T09:00:00Z",
  terms: {
    payout_frequency: "weekly",
    currency: "RUB",
  },
};

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

let portalPayload: PortalMeResponse = financeManagerPortal;
let termsMode: "active" | "missing" = "active";

beforeEach(() => {
  portalPayload = financeManagerPortal;
  termsMode = "active";
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof Request ? input.url : input.toString();
      if (url.includes("/partner/auth/verify")) {
        return Promise.resolve(jsonResponse({ ok: true }));
      }
      if (url.includes("/portal/me")) {
        return Promise.resolve(jsonResponse(portalPayload));
      }
      if (url.includes("/partner/self-profile")) {
        return Promise.resolve(jsonResponse(profilePayload));
      }
      if (url.includes("/partner/users")) {
        return Promise.resolve(jsonResponse(usersPayload));
      }
      if (url.includes("/partner/terms")) {
        if (termsMode === "missing") {
          return Promise.resolve(jsonResponse({ detail: "terms_not_found" }, 404));
        }
        return Promise.resolve(jsonResponse(termsPayload));
      }
      if (url.includes("/partner/locations")) {
        return Promise.resolve(
          jsonResponse([
            {
              id: "loc-1",
              partner_id: "partner-1",
              title: "Сервисный центр",
              address: "Москва, Пример, 1",
              city: "Москва",
              status: "ACTIVE",
            },
          ]),
        );
      }
      return Promise.resolve(jsonResponse({ items: [] }));
    }) as unknown as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Partner profile workspace", () => {
  it("renders editable profile workspace for finance manager", async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/partner/profile"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect((await screen.findAllByText("Профиль партнёра")).length).toBeGreaterThan(0);
    expect(await screen.findByDisplayValue("NEFT Partner")).toBeEnabled();
    expect(screen.getByRole("button", { name: "Сохранить профиль" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Создать обращение" })).toBeInTheDocument();
  });

  it("keeps analyst in read-only profile mode", async () => {
    portalPayload = financeAnalystPortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/partner/profile"]}>
          <App initialSession={{ ...financeSession, email: "analyst@neft.local", roles: ["PARTNER_ANALYST"] }} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByText("Режим только для чтения. Изменять профиль могут owner, manager и finance manager.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Сохранить профиль" })).not.toBeInTheDocument();
  });

  it("shows owner-only user management controls", async () => {
    portalPayload = serviceOwnerPortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/partner/users"]}>
          <App initialSession={serviceSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect((await screen.findAllByText("Пользователи партнёра")).length).toBeGreaterThan(0);
    expect(screen.getByPlaceholderText("manager@partner.ru")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Добавить пользователя" })).toBeInTheDocument();
    expect(screen.getByText("manager@partner.ru")).toBeInTheDocument();
  });

  it("keeps analyst users page read-only", async () => {
    portalPayload = financeAnalystPortal;
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/partner/users"]}>
          <App initialSession={{ ...financeSession, email: "analyst@neft.local", roles: ["PARTNER_ANALYST"] }} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByText("Режим только для чтения. Управлять пользователями может только owner партнёра.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Добавить пользователя" })).not.toBeInTheDocument();
  });

  it("renders structured terms state and support actions", async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/partner/terms"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect((await screen.findAllByText("Условия")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Активных условий нет")).not.toBeInTheDocument();
    expect(await screen.findByText("weekly")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Legal" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Создать обращение" })).toBeInTheDocument();
  });

  it("shows honest empty state when terms are absent", async () => {
    termsMode = "missing";
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/partner/terms"]}>
          <App initialSession={financeSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByText("Активных условий нет")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть профиль" })).toHaveAttribute("href", "/partner/profile");
  });
});

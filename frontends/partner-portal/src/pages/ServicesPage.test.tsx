import { fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession, PortalMeResponse } from "../api/types";
import i18n from "../i18n";

const managerSession: AuthSession = {
  token: "token-1",
  email: "manager@neft.local",
  roles: ["PARTNER_SERVICE_MANAGER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const portalMe: PortalMeResponse = {
  user: {
    id: "user-1",
    email: managerSession.email,
    subject_type: managerSession.subjectType,
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

const mockListResponse = () =>
  new Response(
    JSON.stringify({
      items: [
        {
          id: "catalog-1",
          kind: "SERVICE",
          title: "Мойка",
          description: "Полный комплекс",
          category: "Автомойка",
          baseUom: "услуга",
          status: "DRAFT",
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          activeOffersCount: 0,
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    {
      status: 200,
      headers: { "content-type": "application/json" },
    },
  );

const emptyResponse = () =>
  new Response(JSON.stringify({ items: [] }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

const mockVerifyResponse = () =>
  new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

const mockPortalResponse = () =>
  new Response(JSON.stringify(portalMe), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

const renderPage = () =>
  render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={["/services"]}>
        <App initialSession={managerSession} />
      </MemoryRouter>
    </I18nextProvider>,
  );

beforeEach(() => {
  window.localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/partner/auth/verify")) {
        return Promise.resolve(mockVerifyResponse());
      }
      if (url.includes("/portal/me")) {
        return Promise.resolve(mockPortalResponse());
      }
      if (url.includes("/partner/catalog")) {
        return Promise.resolve(mockListResponse());
      }
      return Promise.resolve(emptyResponse());
    }) as unknown as typeof fetch,
  );
});

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ServicesPage", () => {
  it("renders services list", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Каталог услуг" })).toBeInTheDocument();
    expect(await screen.findByText("Мойка")).toBeInTheDocument();
    expect(await screen.findByText("Автомойка")).toBeInTheDocument();
    expect(screen.getByText("1 / 1")).toBeInTheDocument();
  });

  it("opens create modal", async () => {
    renderPage();

    const createButton = await screen.findByRole("button", { name: /^Создать$/ });
    fireEvent.click(createButton);
    expect(screen.getByRole("heading", { name: "Создать элемент" })).toBeInTheDocument();
  });

  it("shows error state on API failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo) => {
        const url = String(input);
        if (url.includes("/partner/auth/verify")) {
          return Promise.resolve(mockVerifyResponse());
        }
        if (url.includes("/portal/me")) {
          return Promise.resolve(mockPortalResponse());
        }
        return Promise.resolve(
          new Response(JSON.stringify({ error: "fail" }), {
            status: 500,
            headers: { "content-type": "application/json" },
          }),
        );
      }) as unknown as typeof fetch,
    );

    renderPage();

    expect(await screen.findByRole("heading", { name: "Данные временно недоступны" })).toBeInTheDocument();
  });
});

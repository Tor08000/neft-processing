import { fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession, PortalMeResponse } from "../api/types";
import i18n from "../i18n";

const managerSession: AuthSession = {
  token: "token-1",
  email: "manager@demo.test",
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

const mockFetch = (url: string, init?: RequestInit) => {
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
  if (url.includes("/partner/services/service-1") && !url.includes("locations") && init?.method !== "PATCH") {
    return new Response(
      JSON.stringify({
        id: "service-1",
        partner_id: "partner-1",
        title: "Диагностика",
        description: "Полная проверка",
        category: "Auto",
        status: "DRAFT",
        tags: ["engine"],
        attributes: {},
        duration_min: 60,
        requirements: "Документы",
        media: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }
  if (url.includes("/partner/services/service-1/locations")) {
    return new Response(
      JSON.stringify([
        {
          id: "location-1",
          service_id: "service-1",
          location_id: "station-1",
          address: "ул. Тестовая, 1",
          is_active: true,
        },
      ]),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }
  if (url.includes("/partner/locations")) {
    return new Response(
      JSON.stringify([
        {
          id: "station-1",
          partner_id: "partner-1",
          title: "АЗС 1",
          address: "ул. Тестовая, 1",
          status: "ACTIVE",
        },
      ]),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }
  if (url.includes("/partner/service-locations/location-1/schedule") && init?.method !== "POST") {
    return new Response(JSON.stringify({ rules: [], exceptions: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
  if (url.includes("/partner/service-locations/location-1/schedule/rules") && init?.method === "POST") {
    return new Response(
      JSON.stringify({
        id: "rule-1",
        service_location_id: "location-1",
        weekday: 0,
        time_from: "09:00",
        time_to: "18:00",
        slot_duration_min: 60,
        capacity: 2,
      }),
      { status: 201, headers: { "content-type": "application/json" } },
    );
  }
  return new Response(JSON.stringify({}), { status: 200, headers: { "content-type": "application/json" } });
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo, init?: RequestInit) => Promise.resolve(mockFetch(String(input), init))) as unknown as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ServiceDetailsPage", () => {
  it("adds schedule rule and shows it in UI", async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/services/service-1"]}>
          <App initialSession={managerSession} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    const scheduleTab = await screen.findByRole("button", { name: "Расписание" });
    fireEvent.click(scheduleTab);

    const addButton = await screen.findByRole("button", { name: "Добавить правило" });
    fireEvent.click(addButton);

    expect(await screen.findByRole("button", { name: "Удалить" })).toBeInTheDocument();
    expect(screen.queryByText(/Правил нет/)).not.toBeInTheDocument();
  });
});

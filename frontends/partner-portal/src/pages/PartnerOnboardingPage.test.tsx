import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession, PortalMeResponse } from "../api/types";
import i18n from "../i18n";

const session: AuthSession = {
  token: "token-onboarding",
  email: "partner@neft.local",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const onboardingPortal: PortalMeResponse = {
  user: {
    id: "user-1",
    email: session.email,
    subject_type: session.subjectType,
  },
  org_roles: ["PARTNER"],
  user_roles: ["PARTNER_OWNER"],
  capabilities: ["PARTNER_CORE", "PARTNER_PROFILE_MANAGE"],
  access_state: "NEEDS_ONBOARDING",
  access_reason: "partner_onboarding",
  gating: {
    onboarding_enabled: true,
    legal_gate_enabled: true,
  },
  partner: {
    partner_id: "partner-1",
    kind: "GENERAL_PARTNER",
    partner_role: "OWNER",
    partner_roles: ["OWNER"],
    default_route: "/partner/profile",
    workspaces: [
      { code: "support", label: "Support", default_route: "/support/requests" },
      { code: "profile", label: "Profile", default_route: "/partner/profile" },
    ],
    status: "PENDING",
    legal_state: { status: "PENDING", block_reason: "legal_pending" },
  },
};

const onboardingSnapshot = {
  partner: {
    id: "partner-1",
    code: "partner-001",
    legal_name: "Pending Partner",
    brand_name: null,
    partner_type: "OTHER",
    status: "PENDING",
    contacts: {},
  },
  checklist: {
    profile_complete: false,
    legal_documents_accepted: false,
    legal_profile_present: false,
    legal_details_present: false,
    legal_details_complete: false,
    legal_verified: false,
    activation_ready: false,
    blocked_reasons: ["profile_incomplete", "legal_documents_pending", "legal_review_pending"],
    next_step: "profile",
    next_route: "/onboarding",
  },
};

const legalProfileResponse = {
  profile: null,
  checklist: {
    legal_profile: false,
    legal_details: false,
    verified: false,
  },
};

const legalRequiredResponse = {
  subject: { type: "PARTNER", id: "partner-1" },
  required: [
    {
      code: "PARTNER_TERMS",
      title: "Partner terms",
      locale: "ru",
      required_version: "1",
      published_at: null,
      effective_from: "2026-01-01T00:00:00Z",
      content_hash: "hash-1",
      accepted: false,
      accepted_at: null,
    },
  ],
  is_blocked: true,
  enabled: true,
};

const jsonResponse = (body: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof Request ? input.url : input.toString();
      if (url.includes("/partner/auth/verify")) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.includes("/portal/me")) {
        return jsonResponse(onboardingPortal);
      }
      if (url.includes("/partner/onboarding")) {
        return jsonResponse(onboardingSnapshot);
      }
      if (url.includes("/partner/legal/profile")) {
        return jsonResponse(legalProfileResponse);
      }
      if (url.includes("/legal/required")) {
        return jsonResponse(legalRequiredResponse);
      }
      return jsonResponse({});
    }) as unknown as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Partner onboarding route", () => {
  it("redirects home into the mounted onboarding owner route", async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/"]}>
          <App initialSession={session} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(await screen.findByRole("link", { name: "Onboarding" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Legal|\u042e\u0440\u0438\u0434\u0438\u0447\u0435\u0441\u043a\u0438\u0435/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Finance$/i })).not.toBeInTheDocument();
  });

  it("keeps activation blocked until checklist is complete", async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={["/onboarding"]}>
          <App initialSession={session} />
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(
      await screen.findByRole("button", {
        name: /\u0410\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u0442\u044c|activate/i,
      }),
    ).toBeDisabled();
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("FleetIncidentsPage", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("renders incidents list", async () => {
    window.localStorage.setItem("neft.client.mode", "fleet");
    const payload = {
      items: [
        {
          case_id: "case-1",
          title: "Fuel spend spike",
          case_kind: "FLEET_ESCALATION",
          status: "OPEN",
          severity: "HIGH",
          opened_at: "2024-02-10T10:00:00.000Z",
          last_updated_at: "2024-02-10T12:00:00.000Z",
          source: { type: "LIMIT_BREACH", ref_id: "exec-1" },
          scope_type: "CARD",
          scope: { card_alias: "Truck 01" },
          policy_action: "AUTO_BLOCK",
        },
      ],
    };
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/cases")) {
        return Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/incidents"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Fuel spend spike")).toBeInTheDocument();
    expect(screen.getByText("Truck 01")).toBeInTheDocument();
  });
});

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const viewerSession: AuthSession = {
  token: "token-viewer",
  email: "viewer@demo.test",
  roles: ["CLIENT_USER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const managerSession: AuthSession = {
  token: "token-manager",
  email: "manager@demo.test",
  roles: ["CLIENT_FLEET_MANAGER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const adminSession: AuthSession = {
  token: "token-admin",
  email: "admin@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const baseDetails = {
  case_id: "case-1",
  title: "Fuel spend spike",
  case_kind: "FLEET_ESCALATION",
  status: "OPEN",
  severity: "HIGH",
  opened_at: "2024-02-10T10:00:00.000Z",
  last_updated_at: "2024-02-10T12:00:00.000Z",
  source: { type: "LIMIT_BREACH", ref_id: "exec-1" },
  scope: { card_alias: "Truck 01", card_id: "card-1" },
  policy_action: "AUTO_BLOCK",
  explain: {
    rule_name: "Fuel limit",
    observed: "150 000",
    threshold: "120 000",
    occurred_at: "2024-02-10T09:45:00.000Z",
    policy_name: "Daily limits",
    cooldown_seconds: 600,
  },
  timeline: [{ id: "event-1", title: "Policy triggered", timestamp: "2024-02-10T09:45:00.000Z" }],
};

describe("FleetIncidentDetailsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders incident details", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/cases/case-1")) {
        return Promise.resolve(new Response(JSON.stringify(baseDetails), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/incidents/case-1"]}>
        <App initialSession={viewerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Fuel spend spike")).toBeInTheDocument();
    expect(screen.getByText(/Почему это произошло/i)).toBeInTheDocument();
    expect(screen.getByText("Fuel limit")).toBeInTheDocument();
  });

  it("hides action buttons for viewer", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      if (input.toString().includes("/client/fleet/cases/case-1")) {
        return Promise.resolve(new Response(JSON.stringify(baseDetails), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/incidents/case-1"]}>
        <App initialSession={viewerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Fuel spend spike")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Взять в работу/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Закрыть инцидент/i })).not.toBeInTheDocument();
  });

  it("shows start work for manager", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      if (input.toString().includes("/client/fleet/cases/case-1")) {
        return Promise.resolve(new Response(JSON.stringify(baseDetails), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/incidents/case-1"]}>
        <App initialSession={managerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Fuel spend spike")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Взять в работу/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Закрыть инцидент/i })).not.toBeInTheDocument();
  });

  it("validates close modal required fields", async () => {
    const detailsInProgress = { ...baseDetails, status: "IN_PROGRESS" };
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/cases/case-1")) {
        return Promise.resolve(new Response(JSON.stringify(detailsInProgress), { status: 200 }));
      }
      if (url.includes("/client/fleet/cases/case-1/close")) {
        return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/incidents/case-1"]}>
        <App initialSession={adminSession} />
      </MemoryRouter>,
    );

    const closeButton = await screen.findByRole("button", { name: /Закрыть инцидент/i });
    await userEvent.click(closeButton);

    const dialog = await screen.findByRole("dialog");
    const confirmButton = within(dialog).getByRole("button", { name: /Закрыть инцидент/i });
    await userEvent.click(confirmButton);

    expect(await screen.findByText(/Заполните резолюцию/i)).toBeInTheDocument();
  });
});

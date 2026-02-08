import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const managerSession: AuthSession = {
  token: "token-1",
  email: "manager@demo.test",
  roles: ["PARTNER_SERVICE_MANAGER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const mockFetch = (url: string, init?: RequestInit) => {
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
      { status: 200 },
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
      { status: 200 },
    );
  }
  if (url.includes("/partner/stations")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "station-1",
            name: "АЗС 1",
            address: "ул. Тестовая, 1",
            status: "active",
          },
        ],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/partner/service-locations/location-1/schedule") && init?.method !== "POST") {
    return new Response(JSON.stringify({ rules: [], exceptions: [] }), { status: 200 });
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
      { status: 201 },
    );
  }
  return new Response(JSON.stringify({}), { status: 200 });
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
      <MemoryRouter initialEntries={["/services/service-1"]}>
        <App initialSession={managerSession} />
      </MemoryRouter>,
    );

    const scheduleTab = await screen.findByRole("button", { name: "Расписание" });
    fireEvent.click(scheduleTab);

    const addButton = await screen.findByRole("button", { name: "Добавить правило" });
    fireEvent.click(addButton);

    expect(await screen.findByText(/Пн/)).toBeInTheDocument();
    expect(screen.getByText(/09:00–18:00/)).toBeInTheDocument();
  });
});

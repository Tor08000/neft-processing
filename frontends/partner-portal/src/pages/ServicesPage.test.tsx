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

const mockListResponse = () =>
  new Response(
    JSON.stringify({
      items: [
        {
          id: "service-1",
          title: "Мойка",
          category: "Автомойка",
          status: "DRAFT",
          duration_min: 60,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    { status: 200 },
  );

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/partner/services")) {
        return Promise.resolve(mockListResponse());
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    }) as unknown as typeof fetch,
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ServicesPage", () => {
  it("renders services list", async () => {
    render(
      <MemoryRouter initialEntries={["/services"]}>
        <App initialSession={managerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Мойка")).toBeInTheDocument();
    expect(screen.getByText("Автомойка")).toBeInTheDocument();
  });

  it("opens create modal", async () => {
    render(
      <MemoryRouter initialEntries={["/services"]}>
        <App initialSession={managerSession} />
      </MemoryRouter>,
    );

    const createButton = await screen.findByRole("button", { name: "Создать услугу" });
    fireEvent.click(createButton);
    expect(screen.getByText("Новая услуга")).toBeInTheDocument();
  });

  it("shows error state on API failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ error: "fail" }), {
            status: 500,
            headers: { "content-type": "application/json" },
          }),
        ),
      ) as unknown as typeof fetch,
    );

    render(
      <MemoryRouter initialEntries={["/services"]}>
        <App initialSession={managerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Не удалось загрузить каталог услуг/)).toBeInTheDocument();
  });
});

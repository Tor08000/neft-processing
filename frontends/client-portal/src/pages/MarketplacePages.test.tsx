import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

describe("Marketplace pages", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders catalog", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/marketplace/catalog")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: "service-1",
                  title: "Шиномонтаж",
                  category: "Техническое обслуживание",
                  partner_name: "Партнёр 1",
                  price_from: 1200,
                  currency: "RUB",
                },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Шиномонтаж")).toBeInTheDocument();
  });

  it("renders service details", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/marketplace/services/service-1")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: "service-1",
              title: "Шиномонтаж",
              description: "Полный комплекс работ",
              category: "ТО",
              partner: { id: "partner-1", name: "Партнёр 1" },
              offers: [
                { id: "offer-1", price: 1200, currency: "RUB", location_name: "МСК", availability: "always" },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/service-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Шиномонтаж")).toBeInTheDocument();
    expect(screen.getByText(/Доступные офферы/i)).toBeInTheDocument();
  });

  it("renders orders list", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/marketplace/orders")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: "order-1",
                  service_title: "Диагностика",
                  partner_name: "Партнёр 2",
                  created_at: "2024-04-01T10:00:00Z",
                  total_amount: 4500,
                  currency: "RUB",
                  status: "CONFIRMED",
                  documents_status: "PENDING",
                },
              ],
              total: 1,
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/orders"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Диагностика")).toBeInTheDocument();
  });

  it("renders create order modal", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/marketplace/services/service-2")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: "service-2",
              title: "Эвакуация",
              partner: { id: "partner-2", name: "Партнёр 2" },
              offers: [{ id: "offer-2", price: 9000, currency: "RUB" }],
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/service-2"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    const openButton = await screen.findByRole("button", { name: /Заказать услугу/i });
    await userEvent.click(openButton);

    expect(await screen.findByText(/Оформить заказ/i)).toBeInTheDocument();
  });

  it("renders error state with correlation id", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/marketplace/catalog")) {
        return Promise.resolve(
          new Response("Server error", {
            status: 500,
            headers: { "x-correlation-id": "corr-123" },
          }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText(/Server error/i)).toBeInTheDocument());
    expect(screen.getByText(/Код ошибки: 500/i)).toBeInTheDocument();
    expect(screen.getByText(/Correlation ID: corr-123/i)).toBeInTheDocument();
  });
});

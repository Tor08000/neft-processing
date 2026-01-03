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

describe("Marketplace browse page", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders list of products", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/marketplace/products")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: "product-1",
                  type: "SERVICE",
                  title: "Мобильный шиномонтаж",
                  short_description: "Выездная бригада",
                  category: "Service",
                  price_model: "FIXED",
                  price_summary: "12 000 ₽",
                  partner_name: "Партнёр 1",
                  partner_id: "partner-1",
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

    expect(await screen.findByText("Мобильный шиномонтаж")).toBeInTheDocument();
  });

  it("renders empty state", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/marketplace/products")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Маркетплейс пока пуст")).toBeInTheDocument();
  });

  it("applies category filter", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/marketplace/products")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: "product-1",
                  type: "SERVICE",
                  title: "Топливо",
                  category: "Fuel",
                  price_model: "FIXED",
                  price_summary: "12 000 ₽",
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

    const categorySelect = await screen.findByLabelText("Категория");
    await userEvent.selectOptions(categorySelect, "Fuel");

    await waitFor(() => {
      expect(fetchMock.mock.calls.some((call) => call[0].toString().includes("category=Fuel"))).toBe(true);
    });
  });
});

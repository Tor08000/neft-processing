import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const baseSession: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_ADMIN"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const productResponse = {
  id: "product-1",
  type: "SERVICE",
  title: "Техническое обслуживание",
  description: "Полный сервис",
  category: "Service",
  price_model: "FIXED",
  price_summary: "12 000 ₽",
  partner: { id: "partner-1", company_name: "Партнёр 1", verified: true },
  sla_summary: {
    obligations: [
      { metric: "Response time", threshold: 2, comparison: "<=", window: "hours" },
    ],
    penalties: "5% credit",
  },
};

describe("Marketplace product details page", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders SLA section", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/marketplace/products/product-1")) {
        return Promise.resolve(new Response(JSON.stringify(productResponse), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/products/product-1"]}>
        <App initialSession={baseSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Уровень сервиса")).toBeInTheDocument();
    expect(screen.getByText(/Response time/i)).toBeInTheDocument();
  });

  it("hides order button for client user", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/marketplace/products/product-1")) {
        return Promise.resolve(new Response(JSON.stringify(productResponse), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/products/product-1"]}>
        <App initialSession={{ ...baseSession, roles: ["CLIENT_USER"] }} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Техническое обслуживание")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Заказать" })).not.toBeInTheDocument();
  });

  it("shows order button for client admin", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/marketplace/products/product-1")) {
        return Promise.resolve(new Response(JSON.stringify(productResponse), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/marketplace/products/product-1"]}>
        <App initialSession={baseSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "Заказать" })).toBeInTheDocument();
  });
});

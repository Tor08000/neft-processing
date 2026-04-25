import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("FleetCardsPage", () => {
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

  it("renders list", async () => {
    window.localStorage.setItem("neft.client.mode", "fleet");
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/cards")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  id: "card-1",
                  card_alias: "Driver 1",
                  masked_pan: "123456******7890",
                  status: "ACTIVE",
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
      <MemoryRouter initialEntries={["/fleet/cards"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Driver 1")).toBeInTheDocument();
  });

  it("validates add card modal", async () => {
    window.localStorage.setItem("neft.client.mode", "fleet");
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/client/fleet/cards")) {
        return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    render(
      <MemoryRouter initialEntries={["/fleet/cards"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    const openButton = await screen.findByRole("button", { name: /Добавить карту/i });
    await userEvent.click(openButton);

    const maskedInput = await screen.findByPlaceholderText("123456******7890");
    await userEvent.type(maskedInput, "1234");

    const submitButton = screen.getByRole("button", { name: /Создать/i });
    await userEvent.click(submitButton);

    expect(await screen.findByText("Masked PAN: 6 цифр + ****** + 4 цифры")).toBeInTheDocument();
  });
});

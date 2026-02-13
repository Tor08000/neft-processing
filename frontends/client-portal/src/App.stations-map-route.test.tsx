import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { AuthSession } from "./api/types";

vi.mock("./pages/stations/StationsMapPage", () => ({
  StationsMapPage: () => <div>Stations map page mock</div>,
}));

const session: AuthSession = {
  token: "token-1",
  email: "client@demo.test",
  roles: ["CLIENT_USER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const emptyResponse = new Response(JSON.stringify({ items: [] }), { status: 200 });

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(emptyResponse)) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Stations map routes", () => {
  it("opens stations map from canonical route", async () => {
    render(
      <MemoryRouter initialEntries={["/stations-map"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Stations map page mock")).toBeInTheDocument();
  });

  it("redirects legacy logistics route to canonical route", async () => {
    render(
      <MemoryRouter initialEntries={["/logistics/stations-map"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Stations map page mock")).toBeInTheDocument();
  });
});

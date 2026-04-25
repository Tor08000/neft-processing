import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { AuthSession } from "./api/types";
import { AuthProvider } from "./auth/AuthContext";
import { ClientCardsPage } from "./pages/ClientCardsPage";

const session: AuthSession = {
  token: "test.header.payload",
  email: "client@demo.test",
  roles: ["CLIENT_USER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const noPermission = "\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u043f\u0440\u0430\u0432 \u0434\u043b\u044f \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0439.";
const blockLabel = "\u0417\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u0442\u044c";

const emptyResponse = new Response(JSON.stringify({ items: [] }), { status: 200 });

beforeEach(() => {
  vi.stubEnv("VITE_DEMO_MODE", "true");
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(emptyResponse)) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("Client portal shell", () => {
  it("renders client layout and primary navigation", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Client portal/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "\u041e\u0431\u0437\u043e\u0440" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438" }).length).toBeGreaterThan(0);
  });

  it("blocks operations for read-only users", async () => {
    render(
      <MemoryRouter initialEntries={["/operations"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(noPermission)).toBeInTheDocument();
  });

  it("loads cards and allows blocking", async () => {
    const cardsPayload = {
      items: [
        { id: "card-1", pan_masked: "1111", status: "ACTIVE", limits: [] },
        { id: "card-2", pan_masked: "2222", status: "BLOCKED", limits: [] },
      ],
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(cardsPayload), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "BLOCKED" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <MemoryRouter initialEntries={["/cards"]}>
        <AuthProvider initialSession={session}>
          <ClientCardsPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    const cardRow = (await screen.findByText("card-1")).closest("tr");
    expect(cardRow).not.toBeNull();

    await userEvent.click(within(cardRow as HTMLElement).getByRole("button", { name: blockLabel }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/cards/card-1"),
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
    await waitFor(() => expect(screen.getAllByText(/BLOCKED/)).not.toHaveLength(0));
  });
});

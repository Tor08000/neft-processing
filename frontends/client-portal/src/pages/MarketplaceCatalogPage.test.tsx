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

describe("MarketplaceCatalogPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders recommendations block when items exist", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/v1/marketplace/client/recommendations")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  offer_id: "offer-1",
                  title: "Diagnostics",
                  subject_type: "SERVICE",
                  partner_id: "partner-1",
                  category: "Auto",
                  preview: { short: "Short" },
                  reason_hint: "Похоже на то, что вы смотрели",
                },
              ],
              generated_at: "2026-02-08T12:00:00Z",
              ttl_seconds: 300,
            }),
            { status: 200 },
          ),
        );
      }
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

    expect(await screen.findByText("Для вас")).toBeInTheDocument();
    expect(screen.getByText("Diagnostics")).toBeInTheDocument();
  });

  it("opens why modal and shows reasons", async () => {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/v1/marketplace/client/recommendations/why")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              offer_id: "offer-1",
              reasons: [{ code: "RECENT_VIEW", label: "Похоже на то, что вы смотрели" }],
              score_breakdown: [{ signal: "recency_view", value: 5 }],
            }),
            { status: 200 },
          ),
        );
      }
      if (url.includes("/v1/marketplace/client/recommendations")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                {
                  offer_id: "offer-1",
                  title: "Diagnostics",
                  subject_type: "SERVICE",
                  partner_id: "partner-1",
                  category: "Auto",
                  preview: { short: "Short" },
                  reason_hint: "Похоже на то, что вы смотрели",
                },
              ],
              generated_at: "2026-02-08T12:00:00Z",
              ttl_seconds: 300,
            }),
            { status: 200 },
          ),
        );
      }
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

    const whyButton = await screen.findByRole("button", { name: "Почему?" });
    await userEvent.click(whyButton);

    await waitFor(() => expect(screen.getByText("Похоже на то, что вы смотрели")).toBeInTheDocument());
  });
});

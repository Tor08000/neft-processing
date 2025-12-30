import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { AuthSession } from "../api/types";

const ownerSession: AuthSession = {
  token: "token-1",
  email: "owner@demo.test",
  roles: ["PARTNER_OWNER"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const operatorSession: AuthSession = {
  token: "token-2",
  email: "operator@demo.test",
  roles: ["PARTNER_OPERATOR"],
  subjectType: "PARTNER",
  partnerId: "partner-1",
  expiresAt: Date.now() + 1000 * 60 * 60,
};

const mockFetch = (url: string) => {
  if (url.includes("/v1/webhooks/event-types")) {
    return new Response(JSON.stringify({ items: ["payout.*"] }), { status: 200 });
  }
  if (url.includes("/v1/webhooks/subscriptions")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "sub-1",
            endpoint_id: "endpoint-1",
            event_type: "payout.*",
            enabled: true,
            filters: { payout_status: "paid" },
          },
        ],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/v1/webhooks/deliveries/")) {
    return new Response(
      JSON.stringify({
        id: "delivery-1",
        endpoint_id: "endpoint-1",
        event_type: "payout.*",
        status: "FAILED",
        attempt: 2,
        last_http_status: 500,
        latency_ms: 123,
        occurred_at: new Date().toISOString(),
        endpoint_url: "https://hooks.demo/partner",
        envelope: { id: "event-1" },
        headers: { "x-neft-signature": "sig" },
        attempts: [
          {
            attempt: 2,
            http_status: 500,
            error: "Timeout",
            latency_ms: 123,
            next_retry_at: new Date().toISOString(),
            correlation_id: "corr-1",
          },
        ],
        correlation_id: "corr-delivery",
      }),
      { status: 200 },
    );
  }
  if (url.includes("/v1/webhooks/endpoints/") && url.includes("/sla")) {
    return new Response(
      JSON.stringify({
        window: "15m",
        success_ratio: 0.92,
        avg_latency_ms: 820,
        sla_breaches: 3,
      }),
      { status: 200 },
    );
  }
  if (url.includes("/v1/webhooks/endpoints/") && url.includes("/alerts")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "alert-1",
            type: "SLA_BREACH",
            window: "30m",
            created_at: new Date().toISOString(),
          },
        ],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/v1/webhooks/endpoints")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "endpoint-1",
            url: "https://hooks.demo/partner",
            status: "ACTIVE",
            signing_algo: "HMAC_SHA256",
            created_at: new Date().toISOString(),
          },
        ],
      }),
      { status: 200 },
    );
  }
  if (url.includes("/v1/webhooks/deliveries")) {
    return new Response(
      JSON.stringify({
        items: [
          {
            id: "delivery-1",
            endpoint_id: "endpoint-1",
            event_type: "payout.*",
            status: "FAILED",
            attempt: 2,
            last_http_status: 500,
            latency_ms: 123,
            occurred_at: new Date().toISOString(),
          },
        ],
      }),
      { status: 200 },
    );
  }
  return new Response(JSON.stringify({ items: [] }), { status: 200 });
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo) => Promise.resolve(mockFetch(String(input)))) as unknown as typeof fetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Integrations page", () => {
  it("renders integrations page", async () => {
    render(
      <MemoryRouter initialEntries={["/integrations"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Integrations/i)).toBeInTheDocument();
    expect(await screen.findByText(/Subscriptions/i)).toBeInTheDocument();
  });

  it("hides mutating actions for non-owner", async () => {
    render(
      <MemoryRouter initialEntries={["/integrations"]}>
        <App initialSession={operatorSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Integrations/i)).toBeInTheDocument();
    expect(screen.queryByText(/Обновить секрет/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Повторить события/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Пауза/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Retry/i)).not.toBeInTheDocument();
  });

  it("renders delivery health controls for owner", async () => {
    render(
      <MemoryRouter initialEntries={["/integrations"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Delivery Health/i)).toBeInTheDocument();
    expect(await screen.findByText(/Alerts/i)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Повторить события/i })).toBeInTheDocument();
  });

  it("opens replay modal", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/integrations"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    const replayButton = await screen.findByRole("button", { name: /Повторить события/i });
    await user.click(replayButton);

    expect(await screen.findByText(/Replay событий/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/С \(UTC\)/i)).toBeInTheDocument();
  });

  it("opens create endpoint modal", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/integrations"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    const button = await screen.findByRole("button", { name: /Создать endpoint/i });
    await user.click(button);

    expect(await screen.findByText(/Создать endpoint/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/URL/i)).toBeInTheDocument();
  });

  it("renders delivery detail drawer", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/integrations"]}>
        <App initialSession={ownerSession} />
      </MemoryRouter>,
    );

    const detailButton = await screen.findByRole("button", { name: /Detail/i });
    await user.click(detailButton);

    expect(await screen.findByText(/Delivery detail/i)).toBeInTheDocument();
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/https:\/\/hooks\.demo\/partner/)).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuthSession } from "./api/types";

vi.mock("./pages/ClientDocumentsPage", () => ({
  ClientDocumentsPage: () => <div>Legacy Documents Page</div>,
}));

vi.mock("./pages/DocumentsPage", () => ({
  DocumentsPage: () => <div>Canonical Documents Page</div>,
}));

vi.mock("./pages/ClientDocumentDetailsPage", () => ({
  ClientDocumentDetailsPage: ({ mode }: { mode?: "legacy" | "canonical" }) => (
    <div>Document Details Mode: {mode ?? "canonical"}</div>
  ),
}));

import { App } from "./App";

const session: AuthSession = {
  token: "docs-token",
  email: "client@neft.local",
  roles: ["CLIENT_OWNER"],
  subjectType: "CLIENT",
  clientId: "client-1",
  expiresAt: Date.now() + 60 * 60 * 1000,
};

const portalMePayload = {
  user: { id: "u-1", email: "client@neft.local" },
  org: null,
  org_status: null,
  org_roles: [],
  user_roles: [],
  capabilities: [],
  nav_sections: [],
  modules: {},
  features: {},
  access_state: "NEEDS_ONBOARDING",
};

describe("Documents route ownership and legacy detail freeze", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function stubFetch() {
    const fetchMock = vi.fn((input: RequestInfo) => {
      const url = input.toString();
      if (url.includes("/portal/me")) {
        return Promise.resolve(new Response(JSON.stringify(portalMePayload), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);
  }

  it("keeps /documents on the legacy documents page", async () => {
    stubFetch();

    render(
      <MemoryRouter initialEntries={["/documents"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Legacy Documents Page")).toBeInTheDocument();
  });

  it("keeps /documents/:id frozen on the legacy compatibility detail mode", async () => {
    stubFetch();

    render(
      <MemoryRouter initialEntries={["/documents/doc-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Document Details Mode: legacy")).toBeInTheDocument();
  });

  it("keeps /client/documents on the canonical documents page", async () => {
    stubFetch();

    render(
      <MemoryRouter initialEntries={["/client/documents"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Canonical Documents Page")).toBeInTheDocument();
  });

  it("keeps /client/documents/:id on the canonical general document details mode", async () => {
    stubFetch();

    render(
      <MemoryRouter initialEntries={["/client/documents/doc-1"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Document Details Mode: canonical")).toBeInTheDocument();
  });

  it("keeps /finance/documents redirecting into the canonical client documents contour", async () => {
    stubFetch();

    render(
      <MemoryRouter initialEntries={["/finance/documents"]}>
        <App initialSession={session} />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Canonical Documents Page")).toBeInTheDocument();
  });
});

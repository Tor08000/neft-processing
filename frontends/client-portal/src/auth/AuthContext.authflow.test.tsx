import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import * as authApi from "../api/auth";
import * as clientPortalApi from "../api/clientPortal";

function makeJwt(payload: Record<string, unknown> = { iss: "neft-auth" }) {
  const base64url = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  return `${base64url({ alg: "HS256", typ: "JWT" })}.${base64url(payload)}.signature`;
}

function Harness() {
  const auth = useAuth();
  const location = useLocation();

  return (
    <>
      <div data-testid="status">{auth.authStatus}</div>
      <div data-testid="path">{location.pathname}</div>
      <button onClick={() => auth.login({ email: "client@neft.local", password: "client" })}>login</button>
      <button
        onClick={() =>
          auth.activateSession({
            token: makeJwt(),
            refreshToken: undefined,
            email: "new@neft.local",
            roles: ["CLIENT_USER"],
            subjectType: "client_user",
            clientId: "c1",
            expiresAt: Date.now() + 60_000,
          })
        }
      >
        signup
      </button>
    </>
  );
}

function renderHarness(initialEntry = "/login") {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AuthProvider>
        <Harness />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("AuthProvider deterministic flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("login success calls /me once and routes away from login", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ token: makeJwt(), refreshToken: "r1", expiresAt: Date.now() + 60_000 } as never);
    vi.spyOn(authApi, "fetchMe").mockResolvedValue({ email: "client@neft.local", roles: ["CLIENT_USER"], subject_type: "CLIENT", client_id: "c1" } as never);
    vi.spyOn(clientPortalApi, "fetchClientMe").mockResolvedValue({ access_state: "ACTIVE", user: { id: "u1", email: "client@neft.local" }, org_roles: [], user_roles: [], capabilities: [] } as never);

    renderHarness();

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    await waitFor(() => expect(authApi.fetchMe).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(authApi.login).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("path").textContent).toBe("/dashboard"));
  });

  it("demo client bypasses onboarding state and routes to dashboard", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ token: makeJwt(), refreshToken: "r1", expiresAt: Date.now() + 60_000 } as never);
    vi.spyOn(authApi, "fetchMe").mockResolvedValue({ email: "client@neft.local", roles: ["CLIENT_USER"], subject_type: "CLIENT", client_id: "c1" } as never);
    vi.spyOn(clientPortalApi, "fetchClientMe").mockResolvedValue({
      access_state: "NEEDS_ONBOARDING",
      user: { id: "u1", email: "client@neft.local" },
      org_roles: [],
      user_roles: [],
      capabilities: [],
    } as never);

    renderHarness();

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    await waitFor(() => expect(clientPortalApi.fetchClientMe).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("path").textContent).toBe("/dashboard"));
  });

  it("routes onboarding clients to canonical onboarding route once", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ token: makeJwt(), refreshToken: "r1", expiresAt: Date.now() + 60_000 } as never);
    vi.spyOn(authApi, "fetchMe").mockResolvedValue({ email: "client@corp.local", roles: ["CLIENT_USER"], subject_type: "CLIENT", client_id: "c1" } as never);
    vi.spyOn(clientPortalApi, "fetchClientMe").mockResolvedValue({
      access_state: "NEEDS_ONBOARDING",
      user: { id: "u1", email: "client@corp.local" },
      org_roles: [],
      user_roles: [],
      capabilities: [],
    } as never);

    renderHarness();

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    await waitFor(() => expect(clientPortalApi.fetchClientMe).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId("path").textContent).toBe("/onboarding"));
  });

  it("does not navigate when already on canonical onboarding route", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ token: makeJwt(), refreshToken: "r1", expiresAt: Date.now() + 60_000 } as never);
    vi.spyOn(authApi, "fetchMe").mockResolvedValue({ email: "client@corp.local", roles: ["CLIENT_USER"], subject_type: "CLIENT", client_id: "c1" } as never);
    vi.spyOn(clientPortalApi, "fetchClientMe").mockResolvedValue({
      access_state: "NEEDS_ONBOARDING",
      user: { id: "u1", email: "client@corp.local" },
      org_roles: [],
      user_roles: [],
      capabilities: [],
    } as never);

    renderHarness("/onboarding");

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    await waitFor(() => expect(clientPortalApi.fetchClientMe).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("path").textContent).toBe("/onboarding");
  });

  it("/me 401 after login triggers reauth redirect and no login retry", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ token: makeJwt(), refreshToken: "r1", expiresAt: Date.now() + 60_000 } as never);
    vi.spyOn(authApi, "fetchMe").mockRejectedValue(new authApi.UnauthorizedError());

    renderHarness();

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    await waitFor(() => expect(authApi.fetchMe).toHaveBeenCalledTimes(1));
    expect(authApi.login).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("path").textContent).toBe("/login");
  });


  it("signup activation persists token before /me and does not redirect to reauth", async () => {
    localStorage.setItem("access_token", "invalid-token");
    localStorage.setItem("refresh_token", "stale-refresh");
    localStorage.setItem("expires_at", String(Date.now() + 120_000));

    const fetchMeSpy = vi
      .spyOn(authApi, "fetchMe")
      .mockResolvedValue({ email: "new@neft.local", roles: ["CLIENT_USER"], subject_type: "CLIENT", client_id: "c1" } as never);
    vi.spyOn(clientPortalApi, "fetchClientMe").mockResolvedValue({ access_state: "ACTIVE", user: { id: "u1", email: "new@neft.local" }, org_roles: [], user_roles: [], capabilities: [] } as never);

    renderHarness("/register");

    await act(async () => {
      screen.getByRole("button", { name: "signup" }).click();
    });

    await waitFor(() => expect(fetchMeSpy).toHaveBeenCalledTimes(1));
    expect(fetchMeSpy).toHaveBeenCalledWith(expect.any(String));
    const savedToken = localStorage.getItem("access_token");
    expect(savedToken).toBeTruthy();
    expect(savedToken).toContain(".");
    await waitFor(() => expect(screen.getByTestId("path").textContent).toBe("/dashboard"));
  });

  it("blocks duplicate login while auth is in progress", async () => {
    let resolveLogin: ((value: unknown) => void) | null = null;
    const pendingLogin = new Promise((resolve) => {
      resolveLogin = resolve;
    });
    vi.spyOn(authApi, "login").mockImplementation(() => pendingLogin as never);
    vi.spyOn(authApi, "fetchMe").mockResolvedValue({ email: "client@neft.local", roles: ["CLIENT_USER"], subject_type: "CLIENT", client_id: "c1" } as never);
    vi.spyOn(clientPortalApi, "fetchClientMe").mockResolvedValue({ access_state: "ACTIVE", user: { id: "u1", email: "client@neft.local" }, org_roles: [], user_roles: [], capabilities: [] } as never);

    renderHarness();

    await act(async () => {
      const btn = screen.getByRole("button", { name: "login" });
      btn.click();
      btn.click();
    });

    expect(authApi.login).toHaveBeenCalledTimes(1);

    await act(async () => {
      if (resolveLogin) {
        resolveLogin({ token: makeJwt(), refreshToken: "r1", expiresAt: Date.now() + 60_000 });
      }
    });

    await waitFor(() => expect(authApi.fetchMe).toHaveBeenCalledTimes(1));
  });
});

import { act, render, screen, waitFor } from "@testing-library/react";
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
  return (
    <>
      <div data-testid="status">{auth.authStatus}</div>
      <button onClick={() => auth.login({ email: "client@neft.local", password: "client" })}>login</button>
    </>
  );
}

describe("AuthProvider deterministic flow", () => {
  const replaceMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    Object.defineProperty(window, "location", {
      value: { ...window.location, replace: replaceMock },
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("login success calls /me once and routes away from login", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ token: makeJwt(), refreshToken: "r1", expiresAt: Date.now() + 60_000 } as never);
    vi.spyOn(authApi, "fetchMe").mockResolvedValue({ email: "client@neft.local", roles: ["CLIENT_USER"], subject_type: "CLIENT", client_id: "c1" } as never);
    vi.spyOn(clientPortalApi, "fetchClientMe").mockResolvedValue({ access_state: "ACTIVE", user: { id: "u1", email: "client@neft.local" }, org_roles: [], user_roles: [], capabilities: [] } as never);

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    await waitFor(() => expect(authApi.fetchMe).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(authApi.login).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(replaceMock).toHaveBeenCalled());
    expect(replaceMock).not.toHaveBeenCalledWith("/client/login");
  });

  it("/me 401 after login triggers reauth redirect and no login retry", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ token: makeJwt(), refreshToken: "r1", expiresAt: Date.now() + 60_000 } as never);
    vi.spyOn(authApi, "fetchMe").mockRejectedValue(new authApi.UnauthorizedError());

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );

    await act(async () => {
      screen.getByRole("button", { name: "login" }).click();
    });

    await waitFor(() => expect(authApi.fetchMe).toHaveBeenCalledTimes(1));
    expect(authApi.login).toHaveBeenCalledTimes(1);
    expect(replaceMock).not.toHaveBeenCalled();
  });
  it("blocks duplicate login while auth is in progress", async () => {
    let resolveLogin: ((value: unknown) => void) | null = null;
    const pendingLogin = new Promise((resolve) => {
      resolveLogin = resolve;
    });
    vi.spyOn(authApi, "login").mockImplementation(() => pendingLogin as never);
    vi.spyOn(authApi, "fetchMe").mockResolvedValue({ email: "client@neft.local", roles: ["CLIENT_USER"], subject_type: "CLIENT", client_id: "c1" } as never);
    vi.spyOn(clientPortalApi, "fetchClientMe").mockResolvedValue({ access_state: "ACTIVE", user: { id: "u1", email: "client@neft.local" }, org_roles: [], user_roles: [], capabilities: [] } as never);

    render(
      <AuthProvider>
        <Harness />
      </AuthProvider>,
    );

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

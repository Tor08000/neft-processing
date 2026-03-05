import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";

const useAuthMock = vi.fn();
const useClientMock = vi.fn();
const useToastMock = vi.fn();
const navigateMock = vi.fn();
const listSsoIdpsMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => useClientMock(),
}));

vi.mock("../components/Toast/useToast", () => ({
  useToast: () => useToastMock(),
}));

vi.mock("../api/auth", async () => {
  const actual = await vi.importActual("../api/auth");
  return {
    ...actual,
    listSsoIdps: (...args: unknown[]) => listSsoIdpsMock(...args),
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listSsoIdpsMock.mockResolvedValue({ idps: [] });
    useToastMock.mockReturnValue({ toast: null, showToast: vi.fn() });
    useAuthMock.mockReturnValue({
      login: vi.fn().mockResolvedValue(undefined),
      error: null,
      authError: null,
    });
    useClientMock.mockReturnValue({
      portalState: "READY",
      refresh: vi.fn().mockResolvedValue(undefined),
    });
  });

  it("navigates demo client to /client/dashboard after successful login and refresh", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    const refresh = vi.fn().mockResolvedValue(undefined);
    useAuthMock.mockReturnValue({ login, error: null, authError: null });
    useClientMock.mockReturnValue({ portalState: "READY", refresh });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Войти" }));

    await waitFor(() => expect(login).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    expect(navigateMock).toHaveBeenCalledWith("/client/dashboard");
  });

  it("demo client is not routed to onboarding during login completion", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    const refresh = vi.fn().mockResolvedValue(undefined);
    useAuthMock.mockReturnValue({ login, error: null, authError: null });
    useClientMock.mockReturnValue({
      portalState: "READY",
      refresh,
      client: { access_state: "NEEDS_ONBOARDING" },
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Войти" }));

    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    expect(navigateMock).toHaveBeenCalledWith("/client/dashboard");
    expect(navigateMock).not.toHaveBeenCalledWith("/client/onboarding");
  });
});

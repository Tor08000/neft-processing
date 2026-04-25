import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
    vi.stubEnv("VITE_DEMO_MODE", "true");
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

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("shows the client bootstrap password, not the admin password", async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(listSsoIdpsMock).toHaveBeenCalledTimes(1));
    expect(screen.getByDisplayValue("Client123!")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Neft123!")).not.toBeInTheDocument();
  });

  it("does not expose demo credentials when demo mode is disabled", async () => {
    vi.stubEnv("VITE_DEMO_MODE", "false");

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(listSsoIdpsMock).toHaveBeenCalledTimes(1));
    expect(screen.queryByDisplayValue("Client123!")).not.toBeInTheDocument();
    expect(screen.queryByText("Demo password")).not.toBeInTheDocument();
    expect(screen.queryByText("Используйте демо-учётные данные, чтобы продолжить работу.")).not.toBeInTheDocument();
    expect(screen.getByText("Войдите под учётными данными клиента, чтобы продолжить работу.")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
  });

  it("refreshes client state after successful login", async () => {
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
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("does not navigate during login completion", async () => {
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
    expect(navigateMock).not.toHaveBeenCalled();
  });
});

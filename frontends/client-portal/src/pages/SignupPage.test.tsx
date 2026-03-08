import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SignupPage } from "./SignupPage";
import { ApiError } from "../api/http";

const registerMock = vi.fn();
const activateSessionMock = vi.fn();
const showToastMock = vi.fn();
const navigateMock = vi.fn();

vi.mock("../api/auth", async () => {
  const actual = await vi.importActual("../api/auth");
  return {
    ...actual,
    register: (...args: unknown[]) => registerMock(...args),
  };
});

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: null, activateSession: activateSessionMock }),
}));

vi.mock("../components/Toast/useToast", () => ({
  useToast: () => ({ toast: null, showToast: showToastMock }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

describe("SignupPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  const fillAndSubmit = () => {
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "existing@neft.local" } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "Pass123!" } });
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole("button", { name: "Зарегистрироваться" }));
  };

  it("Case A — signup conflict shows message, keeps email, and does not redirect", async () => {
    registerMock.mockRejectedValue(new ApiError("user_exists", 409, null, null, "user_exists", "user_exists"));

    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    );

    fillAndSubmit();

    expect(await screen.findByText("Аккаунт с таким email уже существует")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("existing@neft.local");
    expect(navigateMock).not.toHaveBeenCalledWith("/client/login?reauth=1", expect.anything());
    expect(navigateMock).not.toHaveBeenCalledWith("/client/login", expect.anything());
  });

  it("Case B — signup success activates session", async () => {
    registerMock.mockResolvedValue({
      id: "u1",
      email: "new@neft.local",
      is_active: true,
      access_token: "aaa.bbb.ccc",
      refresh_token: "refresh-1",
      token_type: "bearer",
      expires_in: 3600,
      roles: ["CLIENT_OWNER"],
      subject_type: "client_user",
      client_id: "c1",
    });

    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    );

    fillAndSubmit();

    await waitFor(() => expect(activateSessionMock).toHaveBeenCalledTimes(1));
    expect(activateSessionMock).toHaveBeenCalledWith(
      expect.objectContaining({ token: "aaa.bbb.ccc", refreshToken: "refresh-1", email: "new@neft.local" }),
    );
    expect(navigateMock).not.toHaveBeenCalledWith("/client/login?reauth=1", expect.anything());
  });

  it("Case B2 — signup success supports token fallback field", async () => {
    registerMock.mockResolvedValue({
      id: "u1",
      email: "new@neft.local",
      is_active: true,
      token: "aaa.bbb.ccc",
      expires_in: 3600,
      roles: ["CLIENT_OWNER"],
      subject_type: "client_user",
      client_id: "c1",
    });

    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    );

    fillAndSubmit();

    await waitFor(() => expect(activateSessionMock).toHaveBeenCalledTimes(1));
    expect(activateSessionMock).toHaveBeenCalledWith(expect.objectContaining({ token: "aaa.bbb.ccc" }));
    expect(navigateMock).not.toHaveBeenCalledWith("/client/login?reauth=1", expect.anything());
  });

  it("Case C — stale auth storage + conflict remains local and does not trigger reauth redirect", async () => {
    localStorage.setItem("access_token", "invalid-token");
    localStorage.setItem("refresh_token", "stale-refresh");
    localStorage.setItem("expires_at", String(Date.now() - 10_000));
    registerMock.mockRejectedValue(new ApiError("user_exists", 409, null, null, "user_exists", "user_exists"));

    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    );

    fillAndSubmit();

    expect(await screen.findByText("Аккаунт с таким email уже существует")).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalledWith("/client/login?reauth=1", expect.anything());
    expect(activateSessionMock).not.toHaveBeenCalled();
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { LoginPage } from "./LoginPage";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const mockUseAuth = vi.mocked(useAuth);

describe("Admin LoginPage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it("does not expose admin demo credentials unless demo login is enabled", async () => {
    vi.stubEnv("NEFT_DEMO_LOGIN_ENABLED", "false");
    vi.stubEnv("NEFT_DEMO_ADMIN_PASSWORD", "Neft123!");
    mockUseAuth.mockReturnValue({
      login: vi.fn(),
      error: null,
      accessToken: null,
    } as ReturnType<typeof useAuth>);

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <LoginPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/NEFT Platform/i)).toBeInTheDocument();
    expect(screen.queryByText("Demo password")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("Neft123!")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
  });

  it("redirects after the login token appears without changing hook order", async () => {
    const authState = {
      login: vi.fn(),
      error: null,
      accessToken: null as string | null,
    };
    mockUseAuth.mockReturnValue(authState as ReturnType<typeof useAuth>);

    const renderTree = () => (
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Admin dashboard shell</div>} />
        </Routes>
      </MemoryRouter>
    );

    const { rerender } = render(renderTree());

    expect(await screen.findByText(/NEFT Platform/i)).toBeInTheDocument();

    authState.accessToken = "access-token";
    rerender(renderTree());

    expect(await screen.findByText("Admin dashboard shell")).toBeInTheDocument();
  });
});

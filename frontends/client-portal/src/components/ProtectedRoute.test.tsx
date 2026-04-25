import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProtectedRoute } from "./ProtectedRoute";

const useAuthMock = vi.fn();
const useClientMock = vi.fn();
const useLegalGateMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => useClientMock(),
}));

vi.mock("../auth/LegalGateContext", () => ({
  useLegalGate: () => useLegalGateMock(),
}));

describe("ProtectedRoute", () => {
  beforeEach(() => {
    useClientMock.mockReturnValue({ client: null, isLoading: false });
    useLegalGateMock.mockReturnValue({ isBlocked: false });
  });

  it("redirects unauthenticated users through the canonical login route and preserves returnUrl", () => {
    useAuthMock.mockReturnValue({
      user: null,
      authStatus: "unauthenticated",
      hasClientRole: false,
    });

    const LoginScreen = () => {
      const location = useLocation();
      return (
        <div data-testid="login-screen">
          {location.pathname}
          {location.search}
        </div>
      );
    };

    render(
      <MemoryRouter initialEntries={["/marketplace/orders/order-1?tab=incidents"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/marketplace/orders/:orderId" element={<div>order-screen</div>} />
          </Route>
          <Route path="/login" element={<LoginScreen />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("login-screen")).toHaveTextContent(
      "/login?returnUrl=%2Fmarketplace%2Forders%2Forder-1%3Ftab%3Dincidents",
    );
  });
});

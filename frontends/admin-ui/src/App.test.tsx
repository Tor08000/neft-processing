import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { AdminErrorBoundary } from "./admin/AdminErrorBoundary";

const ThrowingRoute = () => {
  throw new Error("boom");
};

describe("App shell", () => {
  it("renders login page inside providers", async () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/NEFT Platform/i)).toBeInTheDocument();
  });

  it("resets the admin crash boundary when route changes", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    const { rerender } = render(
      <MemoryRouter>
        <AdminErrorBoundary resetKey="/broken">
          <ThrowingRoute />
        </AdminErrorBoundary>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Техническая ошибка/i)).toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <AdminErrorBoundary resetKey="/login">
          <div>Login route recovered</div>
        </AdminErrorBoundary>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Login route recovered")).toBeInTheDocument();
    errorSpy.mockRestore();
  });
});

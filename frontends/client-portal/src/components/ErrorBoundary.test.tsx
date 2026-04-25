import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { ErrorBoundary } from "./ErrorBoundary";

function BrokenPage() {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

  beforeEach(() => {
    consoleErrorSpy.mockClear();
  });

  afterEach(() => {
    consoleErrorSpy.mockClear();
  });

  it("renders a fallback status page for uncaught render errors", () => {
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <BrokenPage />
        </ErrorBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link")).toHaveAttribute("href", "/");
    expect(screen.getByRole("button")).toBeInTheDocument();
    expect(screen.queryByText("boom")).not.toBeInTheDocument();
  });
});

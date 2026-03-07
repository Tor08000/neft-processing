import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { OnboardingCanonicalizer, resolveLogicalRoute } from "./App";

vi.mock("./pages/OnboardingPage", () => ({
  OnboardingPage: () => <div>OnboardingPageMock</div>,
}));

describe("onboarding route resolution", () => {
  it("Case B: canonical onboarding path resolves to onboarding component only", async () => {
    const router = createMemoryRouter([{ path: "*", element: <OnboardingCanonicalizer /> }], {
      initialEntries: ["/onboarding"],
    });

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("OnboardingPageMock")).toBeInTheDocument();
    expect(screen.queryByText("OperationsPageMock")).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/onboarding");
  });

  it("Case C: alias /client/onboarding canonicalizes once to /onboarding", async () => {
    const router = createMemoryRouter([{ path: "*", element: <OnboardingCanonicalizer /> }], {
      initialEntries: ["/client/onboarding"],
    });

    render(<RouterProvider router={router} />);

    expect(await screen.findByText("OnboardingPageMock")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe("/onboarding"));
    expect(router.state.historyAction).toBe("REPLACE");
  });

  it("diagnostics resolver marks onboarding and operations routes correctly", () => {
    expect(resolveLogicalRoute("/client/onboarding")).toBe("onboarding_alias");
    expect(resolveLogicalRoute("/onboarding")).toBe("onboarding");
    expect(resolveLogicalRoute("/operations")).toBe("operations");
  });
});

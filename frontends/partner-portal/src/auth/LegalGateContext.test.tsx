import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LegalGateProvider, useLegalGate } from "./LegalGateContext";

const fetchLegalRequiredMock = vi.fn().mockResolvedValue({
  required: [],
  is_blocked: false,
});

vi.mock("../api/legal", () => ({
  fetchLegalRequired: (...args: unknown[]) => fetchLegalRequiredMock(...args),
  acceptLegalDocument: vi.fn(),
  fetchLegalDocument: vi.fn(),
}));

vi.mock("./AuthContext", () => ({
  useAuth: () => ({ user: { token: "token-1" } }),
}));

vi.mock("./PortalContext", () => ({
  usePortal: () => ({ portal: { gating: { onboarding_enabled: true } } }),
}));

function Consumer({ tick }: { tick: number }) {
  const { required } = useLegalGate();
  return <div data-testid="required-count">{required.length}-{tick}</div>;
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("LegalGateProvider", () => {
  it("fetches legal requirements once per token despite rerenders", async () => {
    const { rerender } = render(
      <MemoryRouter>
        <LegalGateProvider>
          <Consumer tick={0} />
        </LegalGateProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchLegalRequiredMock).toHaveBeenCalledTimes(1));

    rerender(
      <MemoryRouter>
        <LegalGateProvider>
          <Consumer tick={1} />
        </LegalGateProvider>
      </MemoryRouter>,
    );

    rerender(
      <MemoryRouter>
        <LegalGateProvider>
          <Consumer tick={2} />
        </LegalGateProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchLegalRequiredMock).toHaveBeenCalledTimes(1));
  });
});

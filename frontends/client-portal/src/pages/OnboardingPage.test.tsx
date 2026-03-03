import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OnboardingPage } from "./OnboardingPage";
import { UnauthorizedError } from "../api/http";

const useAuthMock = vi.fn();
const useClientMock = vi.fn();
const createOrgMock = vi.fn();
const useToastMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => useClientMock(),
}));

vi.mock("../api/clientPortal", async () => {
  const actual = (await vi.importActual("../api/clientPortal")) as typeof import("../api/clientPortal");
  return {
    ...actual,
    createOrg: (...args: unknown[]) => createOrgMock(...args),
  };
});

vi.mock("../components/Toast/useToast", () => ({
  useToast: () => useToastMock(),
}));

describe("OnboardingPage", () => {
  const user = { token: "aaa.bbb.ccc", email: "user@neft.local", roles: ["CLIENT_OWNER"] };

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({ user });
    useClientMock.mockReturnValue({
      client: {
        access_state: "NEEDS_ONBOARDING",
        org: null,
        org_status: null,
        gating: { onboarding_enabled: true, legal_gate_enabled: false },
        features: { onboarding_enabled: true, legal_gate_enabled: false },
        user: { email: "user@neft.local" },
      },
      refresh: vi.fn().mockResolvedValue(undefined),
      portalState: "READY",
      error: null,
      isLoading: false,
    });
    useToastMock.mockReturnValue({ toast: null, showToast: vi.fn() });
  });

  it("invalid INN with letters shows validation error and does not submit", async () => {
    render(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Полное наименование"), { target: { value: "ООО Нефть" } });
    fireEvent.change(screen.getByLabelText("ИНН"), { target: { value: "вапва" } });
    fireEvent.change(screen.getByLabelText("КПП"), { target: { value: "123456789" } });
    fireEvent.change(screen.getByLabelText("ОГРН"), { target: { value: "1234567890123" } });
    fireEvent.change(screen.getByLabelText("Юридический адрес"), { target: { value: "Москва" } });

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    expect(await screen.findByText("Ожидаются только цифры")).toBeInTheDocument();
    expect(createOrgMock).not.toHaveBeenCalled();
  });

  it("valid onboarding payload submits to onboarding profile endpoint", async () => {
    createOrgMock.mockResolvedValue({ id: "c1", status: "ONBOARDING" });

    render(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Полное наименование"), { target: { value: "ООО Нефть" } });
    fireEvent.change(screen.getByLabelText("ИНН"), { target: { value: "1234567890" } });
    fireEvent.change(screen.getByLabelText("КПП"), { target: { value: "123456789" } });
    fireEvent.change(screen.getByLabelText("ОГРН"), { target: { value: "1234567890123" } });
    fireEvent.change(screen.getByLabelText("Юридический адрес"), { target: { value: "Москва" } });

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    await waitFor(() => expect(createOrgMock).toHaveBeenCalledTimes(1));
    expect(createOrgMock.mock.calls[0][1]).toEqual({
      org_type: "LEGAL",
      name: "ООО Нефть",
      inn: "1234567890",
      kpp: "123456789",
      ogrn: "1234567890123",
      address: "Москва",
    });
  });

  it("onboarding 401 triggers single reauth redirect", async () => {
    const replaceMock = vi.fn();
    Object.defineProperty(window, "location", {
      value: { ...window.location, replace: replaceMock },
      writable: true,
    });
    createOrgMock.mockRejectedValue(new UnauthorizedError());

    render(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Полное наименование"), { target: { value: "ООО Нефть" } });
    fireEvent.change(screen.getByLabelText("ИНН"), { target: { value: "1234567890" } });
    fireEvent.change(screen.getByLabelText("КПП"), { target: { value: "123456789" } });
    fireEvent.change(screen.getByLabelText("ОГРН"), { target: { value: "1234567890123" } });
    fireEvent.change(screen.getByLabelText("Юридический адрес"), { target: { value: "Москва" } });

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/client/login?reauth=1"));
    expect(replaceMock).toHaveBeenCalledTimes(1);
    expect(createOrgMock).toHaveBeenCalledTimes(1);
  });

  it("onboarding submit sends a single request while pending", async () => {
    createOrgMock.mockImplementation(() => new Promise(() => undefined));

    render(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Полное наименование"), { target: { value: "ООО Нефть" } });
    fireEvent.change(screen.getByLabelText("ИНН"), { target: { value: "1234567890" } });
    fireEvent.change(screen.getByLabelText("КПП"), { target: { value: "123456789" } });
    fireEvent.change(screen.getByLabelText("ОГРН"), { target: { value: "1234567890123" } });
    fireEvent.change(screen.getByLabelText("Юридический адрес"), { target: { value: "Москва" } });

    const submit = screen.getByRole("button", { name: "Продолжить" });
    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(createOrgMock).toHaveBeenCalledTimes(1);

    await waitFor(() => expect(createOrgMock).toHaveBeenCalledTimes(1));
  });
});

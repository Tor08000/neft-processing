import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OnboardingPage } from "./OnboardingPage";
import { UnauthorizedError, ValidationError } from "../api/http";

const useAuthMock = vi.fn();
const useClientMock = vi.fn();
const createOrgMock = vi.fn();
const fetchPlansMock = vi.fn();
const useToastMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => useClientMock(),
}));

vi.mock("../api/clientPortal", async () => {
  const actual = await vi.importActual("../api/clientPortal");
  return {
    ...actual,
    createOrg: (...args: unknown[]) => createOrgMock(...args),
    fetchPlans: (...args: unknown[]) => fetchPlansMock(...args),
  };
});

vi.mock("../components/Toast/useToast", () => ({
  useToast: () => useToastMock(),
}));

describe("OnboardingPage", () => {
  const user = { token: "aaa.bbb.ccc", email: "user@neft.local", roles: ["CLIENT_OWNER"] };

  beforeEach(() => {
    vi.clearAllMocks();
    fetchPlansMock.mockResolvedValue([{ id: "1", code: "FREE", title: "Free", is_active: true }]);
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

  it("Case A: valid step 1 advances to plan step", async () => {
    createOrgMock.mockResolvedValue({ status: 200, data: { id: "c1", status: "ONBOARDING" } });

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
    expect(await screen.findByText("Выберите план и модули для вашей компании."))
      .toBeInTheDocument();
  });


  it("submits with blank optional contact fields and advances to step 2", async () => {
    createOrgMock.mockResolvedValue({ status: 200, data: { id: "c1", status: "ONBOARDING" } });

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
    fireEvent.change(screen.getByLabelText("ФИО (необязательно)"), { target: { value: "   " } });
    fireEvent.change(screen.getByLabelText("Должность (необязательно)"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Телефон (необязательно)"), { target: { value: "   " } });
    fireEvent.change(screen.getByLabelText("Email (необязательно)"), { target: { value: "" } });

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
    expect(await screen.findByText("Выберите план и модули для вашей компании.")).toBeInTheDocument();
  });

  it("Case B: invalid step 1 shows validation, does not submit, keeps typed data", async () => {
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
    fireEvent.change(screen.getByLabelText("ФИО (необязательно)"), { target: { value: "Иван Иванов" } });

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    expect(await screen.findByText("Ожидаются только цифры")).toBeInTheDocument();
    expect(screen.getByText("Проверьте корректность заполнения полей")).toBeInTheDocument();
    expect(createOrgMock).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Полное наименование")).toHaveValue("ООО Нефть");
    expect(screen.getByLabelText("ФИО (необязательно)")).toHaveValue("Иван Иванов");
    expect(screen.queryByText("Выберите план и модули для вашей компании.")).not.toBeInTheDocument();
  });

  it("Case C: backend validation error is visible and preserves form values", async () => {
    createOrgMock.mockRejectedValue(new ValidationError("Ошибка валидации", "ИНН уже зарегистрирован"));

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

    expect(await screen.findByText("ИНН уже зарегистрирован")).toBeInTheDocument();
    expect(screen.getByLabelText("Полное наименование")).toHaveValue("ООО Нефть");
    expect(screen.getByLabelText("ИНН")).toHaveValue("1234567890");
    expect(screen.queryByText("Выберите план и модули для вашей компании.")).not.toBeInTheDocument();
  });

  it("Case B: successful step 1 remains on step 2 while refresh is stale/pending", async () => {
    let resolveRefresh: (() => void) | null = null;
    const refreshMock = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveRefresh = resolve;
        }),
    );
    useClientMock.mockReturnValue({
      client: {
        access_state: "NEEDS_ONBOARDING",
        org: null,
        org_status: null,
        gating: { onboarding_enabled: true, legal_gate_enabled: false },
        features: { onboarding_enabled: true, legal_gate_enabled: false },
        user: { email: "user@neft.local" },
      },
      refresh: refreshMock,
      portalState: "READY",
      error: null,
      isLoading: false,
    });
    createOrgMock.mockResolvedValue({ status: 200, data: { id: "c1", status: "ONBOARDING" } });

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

    expect(await screen.findByText("Выберите план и модули для вашей компании.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Полное наименование")).not.toBeInTheDocument();
    expect(refreshMock).toHaveBeenCalledTimes(2);

    resolveRefresh?.();
    await waitFor(() => expect(refreshMock).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Выберите план и модули для вашей компании.")).toBeInTheDocument();
  });


  it("Case C: repeated post-submit backend refreshes cannot regress below step 2", async () => {
    const clientState = {
      access_state: "NEEDS_ONBOARDING",
      org: null,
      org_status: null,
      gating: { onboarding_enabled: true, legal_gate_enabled: false },
      features: { onboarding_enabled: true, legal_gate_enabled: false },
      user: { email: "user@neft.local" },
    };
    useClientMock.mockImplementation(() => ({
      client: clientState,
      refresh: vi.fn().mockResolvedValue(undefined),
      portalState: "READY",
      error: null,
      isLoading: false,
    }));
    createOrgMock.mockResolvedValue({ status: 200, data: { id: "c1", status: "ONBOARDING" } });

    const view = render(
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

    expect(await screen.findByText("Выберите план и модули для вашей компании.")).toBeInTheDocument();

    clientState.access_state = "NEEDS_ONBOARDING";
    view.rerender(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Выберите план и модули для вашей компании.")).toBeInTheDocument());

    clientState.access_state = "NEEDS_PLAN";
    view.rerender(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Выберите план и модули для вашей компании.")).toBeInTheDocument());

    clientState.access_state = "NEEDS_ONBOARDING";
    view.rerender(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("Выберите план и модули для вашей компании.")).toBeInTheDocument());
  });

  it("Case D: local step floor has priority over stale backend onboarding state", async () => {
    const clientState = {
      access_state: "NEEDS_ONBOARDING",
      org: null,
      org_status: null,
      gating: { onboarding_enabled: true, legal_gate_enabled: false },
      features: { onboarding_enabled: true, legal_gate_enabled: false },
      user: { email: "user@neft.local" },
    };
    useClientMock.mockImplementation(() => ({
      client: clientState,
      refresh: vi.fn().mockResolvedValue(undefined),
      portalState: "READY",
      error: null,
      isLoading: false,
    }));
    createOrgMock.mockResolvedValue({ status: 200, data: { id: "c1", status: "ONBOARDING" } });

    const view = render(
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

    expect(await screen.findByText("Выберите план и модули для вашей компании.")).toBeInTheDocument();

    clientState.access_state = "NEEDS_ONBOARDING";
    view.rerender(
      <MemoryRouter>
        <OnboardingPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.queryByLabelText("Полное наименование")).not.toBeInTheDocument();
      expect(screen.getByText("Выберите план и модули для вашей компании.")).toBeInTheDocument();
    });
  });
  it("accepts non-200 success semantics (201 and empty body)", async () => {
    createOrgMock.mockResolvedValueOnce({ status: 201, data: { ok: true } });

    const { unmount } = render(
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

    expect(await screen.findByText("Выберите план и модули для вашей компании.")).toBeInTheDocument();
    unmount();

    createOrgMock.mockResolvedValueOnce({ status: 204, data: {} });

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

    expect(await screen.findByText("Выберите план и модули для вашей компании.")).toBeInTheDocument();
  });

  it("maps backend 422 detail fields to form errors", async () => {
    createOrgMock.mockRejectedValue(
      new ValidationError("Ошибка валидации", {
        detail: [
          { loc: ["body", "name"], msg: "Field required" },
          { loc: ["body", "contact_email"], msg: "Invalid email" },
        ],
      }),
    );

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

    expect(await screen.findByText("Field required")).toBeInTheDocument();
    expect(screen.getByText("Invalid email")).toBeInTheDocument();
    expect(screen.getByText("Ошибка валидации. Проверьте данные формы")).toBeInTheDocument();
    expect(screen.getByDisplayValue("ООО Нефть")).toBeInTheDocument();
    expect(screen.queryByText("Выберите план и модули для вашей компании.")).not.toBeInTheDocument();
  });

  it("maps backend 422 errors array fields to inline messages", async () => {
    createOrgMock.mockRejectedValue(
      new ValidationError("Ошибка валидации", {
        errors: [
          { field: "contact_phone", message: "Некорректный телефон" },
          { field: "legal_address", message: "Укажите юридический адрес" },
        ],
      }),
    );

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
    fireEvent.change(screen.getByLabelText("Телефон (необязательно)"), { target: { value: "+79991234567" } });

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    expect(await screen.findByText("Некорректный телефон")).toBeInTheDocument();
    expect(screen.getByText("Укажите юридический адрес")).toBeInTheDocument();
    expect(screen.getByDisplayValue("+79991234567")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Москва")).toBeInTheDocument();
    expect(screen.queryByText("Выберите план и модули для вашей компании.")).not.toBeInTheDocument();
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
    expect(submit).toBeDisabled();
    fireEvent.click(submit);

    expect(createOrgMock).toHaveBeenCalledTimes(1);

    await waitFor(() => expect(createOrgMock).toHaveBeenCalledTimes(1));
  });

  it("Case B: onboarding mount triggers at most one refresh", async () => {
    const refreshMock = vi.fn().mockResolvedValue(undefined);
    useClientMock.mockReturnValue({
      client: {
        access_state: "NEEDS_ONBOARDING",
        org: null,
        org_status: null,
        gating: { onboarding_enabled: true, legal_gate_enabled: false },
        features: { onboarding_enabled: true, legal_gate_enabled: false },
        user: { email: "user@neft.local" },
      },
      refresh: refreshMock,
      portalState: "READY",
      error: null,
      isLoading: false,
    });

    render(
      <MemoryRouter initialEntries={["/client/onboarding"]}>
        <OnboardingPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Онбординг клиента")).toBeInTheDocument());
    await waitFor(() => expect(refreshMock).toHaveBeenCalledTimes(1));
  });

  it("Case C: demo onboarding entry stays on onboarding route", async () => {
    useAuthMock.mockReturnValue({ user: { token: "aaa.bbb.ccc", email: "demo@demo.neft", roles: ["CLIENT_OWNER"] } });
    useClientMock.mockReturnValue({
      client: {
        access_state: "NEEDS_ONBOARDING",
        org: null,
        org_status: null,
        gating: { onboarding_enabled: true, legal_gate_enabled: false },
        features: { onboarding_enabled: true, legal_gate_enabled: false },
        user: { email: "demo@demo.neft" },
      },
      refresh: vi.fn().mockResolvedValue(undefined),
      portalState: "READY",
      error: null,
      isLoading: false,
    });

    render(
      <MemoryRouter initialEntries={["/client/onboarding"]}>
        <OnboardingPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Онбординг клиента")).toBeInTheDocument());
    expect(screen.queryByText("Демо-режим: онбординг пропущен")).not.toBeInTheDocument();
  });

});

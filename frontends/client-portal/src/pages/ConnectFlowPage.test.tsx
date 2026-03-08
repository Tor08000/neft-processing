import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ConnectProfilePage, getProfileFields } from "./ConnectFlowPage";

const updateDraftMock = vi.fn();
const refreshMock = vi.fn().mockResolvedValue(undefined);
const createOrgMock = vi.fn().mockResolvedValue({});
const navigateMock = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { email: "u@neft.local" } }),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => ({ refresh: refreshMock }),
}));

vi.mock("../auth/ClientJourneyContext", () => ({
  useClientJourney: () => ({
    draft: { customerType: "INDIVIDUAL" },
    updateDraft: updateDraftMock,
  }),
}));

vi.mock("../api/clientPortal", () => ({
  createOrg: (...args: unknown[]) => createOrgMock(...args),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

describe("ConnectProfilePage", () => {

  it("returns required fields for all customer types", () => {
    expect(getProfileFields("INDIVIDUAL")).toEqual(["fullName", "phone", "email", "address"]);
    expect(getProfileFields("SOLE_PROPRIETOR")).toEqual(["fullName", "inn", "ogrnip", "address", "contact"]);
    expect(getProfileFields("LEGAL_ENTITY")).toEqual(["legalName", "inn", "kpp", "ogrn", "address", "contact"]);
  });
  it("renders individual required fields", () => {
    render(
      <MemoryRouter>
        <ConnectProfilePage />
      </MemoryRouter>,
    );

    expect(screen.getByPlaceholderText("ФИО")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Телефон")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Адрес")).toBeInTheDocument();
  });

  it("shows validation errors and preserves state", async () => {
    render(
      <MemoryRouter>
        <ConnectProfilePage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    expect(await screen.findByText("Заполните обязательные поля.")).toBeInTheDocument();

    const nameInput = screen.getByPlaceholderText("ФИО") as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "Иван Иванов" } });
    expect(nameInput.value).toBe("Иван Иванов");
  });

  it("submits valid profile and advances", async () => {
    render(
      <MemoryRouter>
        <ConnectProfilePage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByPlaceholderText("ФИО"), { target: { value: "Иван Иванов" } });
    fireEvent.change(screen.getByPlaceholderText("Телефон"), { target: { value: "+79990000000" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "u@neft.local" } });
    fireEvent.change(screen.getByPlaceholderText("Адрес"), { target: { value: "Москва" } });

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    await waitFor(() => expect(createOrgMock).toHaveBeenCalledTimes(1));
    expect(updateDraftMock).toHaveBeenCalledWith({ profileCompleted: true, documentsGenerated: false, documentsViewed: false });
    expect(navigateMock).toHaveBeenCalledWith("/connect/documents");
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ConnectPlanPage,
  ConnectProfilePage,
  ConnectSignPage,
  ConnectTypePage,
  getProfileFields,
} from "./ConnectFlowPage";

const updateDraftMock = vi.fn();
const refreshMock = vi.fn().mockResolvedValue(undefined);
const createOrgMock = vi.fn().mockResolvedValue({});
const navigateMock = vi.fn();

const journeyState = {
  state: "NEEDS_PLAN",
  nextRoute: "/connect/plan",
  draft: { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_START", profileData: {} as Record<string, string> },
  updateDraft: updateDraftMock,
};

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { email: "u@neft.local" } }),
}));

vi.mock("../auth/ClientContext", () => ({
  useClient: () => ({ refresh: refreshMock }),
}));

vi.mock("../auth/ClientJourneyContext", () => ({
  useClientJourney: () => journeyState,
}));

vi.mock("../api/clientPortal", () => ({
  createOrg: (...args: unknown[]) => createOrgMock(...args),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

describe("Connect flow pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    journeyState.draft = { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_START", profileData: {} };
  });

  it("returns required fields for all customer types", () => {
    expect(getProfileFields("INDIVIDUAL")).toEqual(["fullName", "phone", "email", "address"]);
    expect(getProfileFields("SOLE_PROPRIETOR")).toEqual(["fullName", "inn", "ogrnip", "address", "contact"]);
    expect(getProfileFields("LEGAL_ENTITY")).toEqual(["legalName", "inn", "kpp", "ogrn", "address", "contact"]);
  });

  it("renders plan cards and lets user choose plan", () => {
    render(
      <MemoryRouter>
        <ConnectPlanPage />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("plan-card-CLIENT_FREE_TRIAL")).toBeInTheDocument();
    expect(screen.getByTestId("plan-card-CLIENT_ENTERPRISE")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Choose plan: Trial/i }));
    expect(updateDraftMock).toHaveBeenCalledWith({ selectedPlan: "CLIENT_FREE_TRIAL", subscriptionState: "TRIAL_PENDING" });
    expect(navigateMock).toHaveBeenCalledWith("/connect/type");
  });

  it("renders all customer type choices", () => {
    render(
      <MemoryRouter>
        <ConnectTypePage />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("type-option-INDIVIDUAL")).toBeInTheDocument();
    expect(screen.getByTestId("type-option-SOLE_PROPRIETOR")).toBeInTheDocument();
    expect(screen.getByTestId("type-option-LEGAL_ENTITY")).toBeInTheDocument();
  });

  it("renders type-specific profile fields and keeps values", () => {
    journeyState.draft = { customerType: "LEGAL_ENTITY", selectedPlan: "CLIENT_START", profileData: { legalName: "ООО Тест" } };

    render(
      <MemoryRouter>
        <ConnectProfilePage />
      </MemoryRouter>,
    );

    expect(screen.getByPlaceholderText("Legal company name")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Full name")).not.toBeInTheDocument();
    expect((screen.getByPlaceholderText("Legal company name") as HTMLInputElement).value).toBe("ООО Тест");

    fireEvent.change(screen.getByPlaceholderText("INN"), { target: { value: "123" } });
    expect(updateDraftMock).toHaveBeenCalledWith({ profileData: { legalName: "ООО Тест", inn: "123" } });
  });

  it("shows validation errors and preserves input", async () => {
    render(
      <MemoryRouter>
        <ConnectProfilePage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findAllByText("This field is required")).not.toHaveLength(0);

    const nameInput = screen.getByPlaceholderText("Full name") as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "Иван Иванов" } });
    expect(nameInput.value).toBe("Иван Иванов");
  });

  it("submits profile and moves to documents", async () => {
    render(
      <MemoryRouter>
        <ConnectProfilePage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByPlaceholderText("Full name"), { target: { value: "Иван Иванов" } });
    fireEvent.change(screen.getByPlaceholderText("Phone"), { target: { value: "+79990000000" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "u@neft.local" } });
    fireEvent.change(screen.getByPlaceholderText("Address"), { target: { value: "Москва" } });

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(createOrgMock).toHaveBeenCalledTimes(1));
    expect(updateDraftMock).toHaveBeenCalledWith(expect.objectContaining({ profileCompleted: true, documentsGenerated: false, documentsViewed: false }));
    expect(navigateMock).toHaveBeenCalledWith("/connect/documents");
  });

  it("free trial signature skips payment", () => {
    journeyState.draft = { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_FREE_TRIAL", profileData: {}, signAccepted: true };

    render(
      <MemoryRouter>
        <ConnectSignPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Sign and continue" }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard");
  });

  it("paid signature opens payment", () => {
    journeyState.draft = { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_START", profileData: {}, signAccepted: true };

    render(
      <MemoryRouter>
        <ConnectSignPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Sign and continue" }));
    expect(navigateMock).toHaveBeenCalledWith("/connect/payment");
  });
});

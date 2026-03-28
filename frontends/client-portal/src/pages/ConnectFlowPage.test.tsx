import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ConnectDocumentsPage,
  ConnectPaymentPage,
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

vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: { email: "u@neft.local" } }) }));
vi.mock("../auth/ClientContext", () => ({ useClient: () => ({ refresh: refreshMock }) }));
vi.mock("../auth/ClientJourneyContext", () => ({ useClientJourney: () => journeyState }));
vi.mock("../api/clientPortal", () => ({ createOrg: (...args: unknown[]) => createOrgMock(...args) }));
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

describe("Connect flow pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    journeyState.state = "NEEDS_PLAN";
    journeyState.nextRoute = "/connect/plan";
    journeyState.draft = { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_START", profileData: {}, subscriptionState: "PAYMENT_PENDING" };
  });

  it("returns required fields for all customer types", () => {
    expect(getProfileFields("INDIVIDUAL")).toEqual(["fullName", "phone", "email", "address"]);
    expect(getProfileFields("SOLE_PROPRIETOR")).toEqual(["fullName", "inn", "ogrnip", "address", "contact"]);
    expect(getProfileFields("LEGAL_ENTITY")).toEqual(["legalName", "inn", "kpp", "ogrn", "address", "contact"]);
  });

  it("renders plan cards and lets user choose plan", () => {
    render(<MemoryRouter><ConnectPlanPage /></MemoryRouter>);
    expect(screen.getByTestId("plan-card-CLIENT_FREE_TRIAL")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Choose plan: Trial/i }));
    expect(updateDraftMock).toHaveBeenCalledWith({ selectedPlan: "CLIENT_FREE_TRIAL", subscriptionState: "TRIAL_PENDING" });
    expect(navigateMock).toHaveBeenCalledWith("/connect/type");
  });

  it("renders all customer type choices", () => {
    render(<MemoryRouter><ConnectTypePage /></MemoryRouter>);
    expect(screen.getByTestId("type-option-INDIVIDUAL")).toBeInTheDocument();
    expect(screen.getByTestId("type-option-SOLE_PROPRIETOR")).toBeInTheDocument();
    expect(screen.getByTestId("type-option-LEGAL_ENTITY")).toBeInTheDocument();
  });

  it("submits profile and moves to documents", async () => {
    render(<MemoryRouter><ConnectProfilePage /></MemoryRouter>);
    fireEvent.change(screen.getByPlaceholderText("Full name"), { target: { value: "Иван Иванов" } });
    fireEvent.change(screen.getByPlaceholderText("Phone"), { target: { value: "+79990000000" } });
    fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "u@neft.local" } });
    fireEvent.change(screen.getByPlaceholderText("Address"), { target: { value: "Москва" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(createOrgMock).toHaveBeenCalledTimes(1));
    expect(updateDraftMock).toHaveBeenCalledWith(expect.objectContaining({ profileCompleted: true, documentsGenerated: false, documentsViewed: false }));
    expect(navigateMock).toHaveBeenCalledWith("/connect/documents");
  });

  it("documents step renders required docs and blocks until reviewed", () => {
    journeyState.state = "NEEDS_DOCUMENTS";
    journeyState.draft = { customerType: "LEGAL_ENTITY", selectedPlan: "CLIENT_START", profileData: { legalName: "ООО Тест" }, documentsGenerated: true, documentsViewed: false };

    render(<MemoryRouter><ConnectDocumentsPage /></MemoryRouter>);

    expect(screen.getByTestId("document-service_agreement")).toBeInTheDocument();
    expect(screen.getByTestId("document-corporate_requisites")).toBeInTheDocument();

    const continueButton = screen.getByRole("button", { name: "Continue to signature" });
    expect(continueButton).toBeDisabled();

    const reviewButtons = screen.getAllByRole("button", { name: "Mark as reviewed" });
    reviewButtons.forEach((button) => fireEvent.click(button));

    expect(updateDraftMock).toHaveBeenCalledWith(expect.objectContaining({ documentsGenerated: true }));
    expect(continueButton).toBeDisabled();
  });

  it("sign step requires acceptance before progression", () => {
    journeyState.state = "NEEDS_SIGNATURE";
    journeyState.draft = { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_START", profileData: {}, signAccepted: false };

    render(<MemoryRouter><ConnectSignPage /></MemoryRouter>);

    const proceedButton = screen.getByRole("button", { name: "Sign and continue" });
    expect(proceedButton).toBeDisabled();

    fireEvent.click(screen.getByLabelText(/I have reviewed and accept the documents/i));
    expect(proceedButton).toBeDisabled();

    fireEvent.click(screen.getByLabelText(/I agree to proceed/i));
    expect(proceedButton).toBeEnabled();

    fireEvent.click(proceedButton);
    expect(navigateMock).toHaveBeenCalledWith("/connect/payment");
  });

  it("free trial signature skips payment", () => {
    journeyState.draft = { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_FREE_TRIAL", profileData: {}, signAccepted: true };
    render(<MemoryRouter><ConnectSignPage /></MemoryRouter>);

    fireEvent.click(screen.getByLabelText(/I agree to proceed/i));
    fireEvent.click(screen.getByRole("button", { name: "Sign and continue" }));
    expect(navigateMock).toHaveBeenCalledWith("/dashboard");
  });

  it("payment failure remains on payment with retry option", () => {
    journeyState.state = "NEEDS_PAYMENT";
    journeyState.draft = { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_START", profileData: {}, subscriptionState: "PAYMENT_PENDING" };
    render(<MemoryRouter><ConnectPaymentPage /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "Simulate payment failure" }));
    expect(updateDraftMock).toHaveBeenCalledWith({ subscriptionState: "PAYMENT_FAILED" });
  });

  it("payment success transitions to active dashboard", () => {
    journeyState.state = "NEEDS_PAYMENT";
    journeyState.draft = { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_START", profileData: {}, subscriptionState: "PAYMENT_PROCESSING" };
    render(<MemoryRouter><ConnectPaymentPage /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "Simulate payment success" }));
    expect(updateDraftMock).toHaveBeenCalledWith({ subscriptionState: "ACTIVE" });
    expect(navigateMock).toHaveBeenCalledWith("/dashboard");
  });

  it("free trial payment page shows skip path", () => {
    journeyState.state = "TRIAL_ACTIVE";
    journeyState.draft = { customerType: "INDIVIDUAL", selectedPlan: "CLIENT_FREE_TRIAL", profileData: {}, subscriptionState: "TRIAL_PENDING" };
    render(<MemoryRouter><ConnectPaymentPage /></MemoryRouter>);

    expect(screen.getByText(/Payment is skipped for free trial/i)).toBeInTheDocument();
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ClientDetailsPage from "./ClientDetailsPage";
import ContractDetailsPage from "./ContractDetailsPage";
import SubscriptionCfoExplainPage from "./SubscriptionCfoExplainPage";
import SubscriptionDetailsPage from "./SubscriptionDetailsPage";
import SubscriptionPreviewBillingPage from "./SubscriptionPreviewBillingPage";
import TariffDetailsPage from "./TariffDetailsPage";

const useAuthMock = vi.fn();
const showToastMock = vi.fn();
const getContractMock = vi.fn();
const listLimitProfilesMock = vi.fn();
const listRiskProfilesMock = vi.fn();
const getClientMock = vi.fn();
const getClientDecisionContextMock = vi.fn();
const listContractsMock = vi.fn();
const listSubscriptionsMock = vi.fn();
const getClientFeaturesMock = vi.fn();
const getSubscriptionMock = vi.fn();
const subscriptionCfoExplainMock = vi.fn();
const getTariffMock = vi.fn();
const previewSubscriptionBillingMock = vi.fn();

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("../../components/Toast/useToast", () => ({
  useToast: () => ({
    toast: null,
    showToast: showToastMock,
  }),
}));

vi.mock("../../components/common/Toast", () => ({
  Toast: () => null,
}));

vi.mock("../../components/common/JsonViewer", () => ({
  JsonViewer: () => <div data-testid="json-viewer" />,
}));

vi.mock("../../components/common/Tabs", () => ({
  Tabs: () => <div data-testid="tabs" />,
}));

vi.mock("../../components/common/DataTable", () => ({
  DataTable: ({ emptyMessage }: { emptyMessage?: string }) => <div>{emptyMessage ?? "table"}</div>,
}));

vi.mock("../../components/common/ConfirmModal", () => ({
  ConfirmModal: () => null,
}));

vi.mock("../../components/crm/ContractForm", () => ({
  ContractForm: () => <div data-testid="contract-form" />,
}));

vi.mock("../../components/crm/ClientForm", () => ({
  ClientForm: () => <div data-testid="client-form" />,
}));

vi.mock("../../components/crm/SubscriptionForm", () => ({
  SubscriptionForm: () => <div data-testid="subscription-form" />,
}));

vi.mock("../../components/crm/FeatureFlagsPanel", () => ({
  FeatureFlagsPanel: () => <div data-testid="feature-flags-panel" />,
}));

vi.mock("../../components/StatusBadge/StatusBadge", () => ({
  StatusBadge: ({ status }: { status: string }) => <span>{status}</span>,
}));

vi.mock("../../api/crm", () => ({
  getContract: (...args: unknown[]) => getContractMock(...args),
  listLimitProfiles: (...args: unknown[]) => listLimitProfilesMock(...args),
  listRiskProfiles: (...args: unknown[]) => listRiskProfilesMock(...args),
  activateContract: vi.fn(),
  pauseContract: vi.fn(),
  terminateContract: vi.fn(),
  applyContract: vi.fn(),
  updateContract: vi.fn(),
  getClient: (...args: unknown[]) => getClientMock(...args),
  getClientDecisionContext: (...args: unknown[]) => getClientDecisionContextMock(...args),
  listContracts: (...args: unknown[]) => listContractsMock(...args),
  listSubscriptions: (...args: unknown[]) => listSubscriptionsMock(...args),
  getClientFeatures: (...args: unknown[]) => getClientFeaturesMock(...args),
  updateClient: vi.fn(),
  enableFeature: vi.fn(),
  disableFeature: vi.fn(),
  getSubscription: (...args: unknown[]) => getSubscriptionMock(...args),
  updateSubscription: vi.fn(),
  subscriptionCfoExplain: (...args: unknown[]) => subscriptionCfoExplainMock(...args),
  getTariff: (...args: unknown[]) => getTariffMock(...args),
  updateTariff: vi.fn(),
  previewSubscriptionBilling: (...args: unknown[]) => previewSubscriptionBillingMock(...args),
}));

const renderRoute = (initialEntry: string, routePath: string, element: React.ReactNode) =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path={routePath} element={element} />
      </Routes>
    </MemoryRouter>,
  );

describe("CRM detail pages", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "admin-token" });
    listLimitProfilesMock.mockResolvedValue({ items: [] });
    listRiskProfilesMock.mockResolvedValue({ items: [] });
    getClientDecisionContextMock.mockResolvedValue({});
    listContractsMock.mockResolvedValue({ items: [] });
    listSubscriptionsMock.mockResolvedValue({ items: [] });
    getClientFeaturesMock.mockResolvedValue({});
  });

  it("shows retryable error state on contract detail load failure", async () => {
    getContractMock.mockRejectedValueOnce(new Error("contract exploded")).mockResolvedValueOnce({
      id: "contract-1",
      contract_id: "contract-1",
      contract_number: "CNT-001",
      client_id: "client-1",
      status: "ACTIVE",
      documents_required: true,
    });

    renderRoute("/crm/contracts/contract-1", "/crm/contracts/:id", <ContractDetailsPage />);

    expect(await screen.findByText("Failed to load contract detail")).toBeInTheDocument();
    expect(screen.getByText("contract exploded")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(getContractMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Contract CNT-001")).toBeInTheDocument();
  });

  it("shows honest not-found state on missing client detail", async () => {
    getClientMock.mockResolvedValue(null);

    renderRoute("/crm/clients/client-404", "/crm/clients/:id", <ClientDetailsPage />);

    expect(await screen.findByText("Client not found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to clients" })).toBeInTheDocument();
  });

  it("shows retryable error state on subscription detail load failure", async () => {
    getSubscriptionMock.mockRejectedValueOnce(new Error("subscription exploded")).mockResolvedValueOnce({
      id: "sub-1",
      subscription_id: "sub-1",
      client_id: "client-1",
      status: "ACTIVE",
    });

    renderRoute("/crm/subscriptions/sub-1", "/crm/subscriptions/:id", <SubscriptionDetailsPage />);

    expect(await screen.findByText("Failed to load subscription detail")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(getSubscriptionMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Subscription sub-1")).toBeInTheDocument();
  });

  it("requires period_id before rendering CFO explain data", async () => {
    renderRoute(
      "/crm/subscriptions/sub-1/cfo-explain",
      "/crm/subscriptions/:id/cfo-explain",
      <SubscriptionCfoExplainPage />,
    );

    expect(await screen.findByText("Period ID is required")).toBeInTheDocument();
    expect(subscriptionCfoExplainMock).not.toHaveBeenCalled();
  });

  it("shows honest not-found state on missing tariff detail", async () => {
    getTariffMock.mockResolvedValue(null);

    renderRoute("/crm/tariffs/tariff-404", "/crm/tariffs/:id", <TariffDetailsPage />);

    expect(await screen.findByText("Tariff not found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to tariffs" })).toBeInTheDocument();
  });

  it("shows period prompt before preview billing is requested", async () => {
    renderRoute(
      "/crm/subscriptions/sub-1/preview-billing",
      "/crm/subscriptions/:id/preview-billing",
      <SubscriptionPreviewBillingPage />,
    );

    expect(await screen.findByText("Period ID is required")).toBeInTheDocument();
    expect(previewSubscriptionBillingMock).not.toHaveBeenCalled();
  });
});

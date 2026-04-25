import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ClientsPage from "./ClientsPage";
import ContractsPage from "./ContractsPage";
import SubscriptionsPage from "./SubscriptionsPage";
import TariffsPage from "./TariffsPage";

const useAuthMock = vi.fn();
const showToastMock = vi.fn();
const listClientsMock = vi.fn();
const listContractsMock = vi.fn();
const listLimitProfilesMock = vi.fn();
const listRiskProfilesMock = vi.fn();
const listSubscriptionsMock = vi.fn();
const listTariffsMock = vi.fn();

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

vi.mock("../../api/crm", () => ({
  listClients: (...args: unknown[]) => listClientsMock(...args),
  createClient: vi.fn(),
  listContracts: (...args: unknown[]) => listContractsMock(...args),
  createContract: vi.fn(),
  activateContract: vi.fn(),
  pauseContract: vi.fn(),
  terminateContract: vi.fn(),
  applyContract: vi.fn(),
  listLimitProfiles: (...args: unknown[]) => listLimitProfilesMock(...args),
  listRiskProfiles: (...args: unknown[]) => listRiskProfilesMock(...args),
  listSubscriptions: (...args: unknown[]) => listSubscriptionsMock(...args),
  createSubscription: vi.fn(),
  pauseSubscription: vi.fn(),
  resumeSubscription: vi.fn(),
  cancelSubscription: vi.fn(),
  listTariffs: (...args: unknown[]) => listTariffsMock(...args),
  createTariff: vi.fn(),
}));

describe("CRM list pages", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthMock.mockReturnValue({ accessToken: "admin-token" });
  });

  it("renders shared toolbar and footer on clients list", async () => {
    listClientsMock.mockResolvedValue({
      items: [
        {
          id: "client-1",
          client_id: "client-1",
          legal_name: "ООО Нефть",
          status: "ACTIVE",
          country: "RU",
          timezone: "Europe/Moscow",
        },
      ],
    });

    render(
      <MemoryRouter>
        <ClientsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("ООО Нефть")).toBeInTheDocument();
    expect(screen.getByLabelText("Search")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create client" })).toBeInTheDocument();
    expect(screen.getByText("Rows: 1")).toBeInTheDocument();
  });

  it("shows filtered-empty reset on clients list", async () => {
    listClientsMock
      .mockResolvedValueOnce({
        items: [
          {
            id: "client-1",
            client_id: "client-1",
            legal_name: "ООО Нефть",
            status: "ACTIVE",
            country: "RU",
            timezone: "Europe/Moscow",
          },
        ],
      })
      .mockResolvedValueOnce({
        items: [],
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: "client-1",
            client_id: "client-1",
            legal_name: "ООО Нефть",
            status: "ACTIVE",
            country: "RU",
            timezone: "Europe/Moscow",
          },
        ],
      });

    render(
      <MemoryRouter>
        <ClientsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("ООО Нефть")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "missing-client" } });

    expect(await screen.findByText("Clients not found")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));

    expect(await screen.findByText("ООО Нефть")).toBeInTheDocument();
  });

  it("renders lifecycle row actions on contracts list", async () => {
    listContractsMock.mockResolvedValue({
      items: [
        {
          id: "contract-1",
          contract_id: "contract-1",
          contract_number: "CNT-001",
          client_id: "client-1",
          status: "ACTIVE",
          valid_from: "2026-04-01",
          valid_to: "2026-12-31",
          billing_mode: "POSTPAID",
          currency: "RUB",
          risk_profile_id: "risk-1",
          limit_profile_id: "limit-1",
          documents_required: true,
        },
      ],
    });
    listLimitProfilesMock.mockResolvedValue({ items: [] });
    listRiskProfilesMock.mockResolvedValue({ items: [] });

    render(
      <MemoryRouter>
        <ContractsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("CNT-001")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Activate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Terminate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
    expect(screen.getByText("Rows: 1")).toBeInTheDocument();
  });

  it("renders retryable shared error state on subscriptions list", async () => {
    listSubscriptionsMock.mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce({ items: [] });

    render(
      <MemoryRouter>
        <SubscriptionsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Не удалось загрузить подписки")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create subscription" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(listSubscriptionsMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Subscriptions not created yet")).toBeInTheDocument();
  });

  it("renders shared footer on tariffs list", async () => {
    listTariffsMock.mockResolvedValue({
      items: [
        {
          id: "tariff-1",
          tariff_id: "tariff-1",
          name: "Enterprise",
          status: "ACTIVE",
          billing_period: "MONTH",
          base_fee_minor: 120000,
          currency: "RUB",
          features: { analytics: true },
        },
      ],
    });

    render(
      <MemoryRouter>
        <TariffsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Enterprise")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create tariff" })).toBeInTheDocument();
    expect(screen.getByText("Rows: 1")).toBeInTheDocument();
  });
});

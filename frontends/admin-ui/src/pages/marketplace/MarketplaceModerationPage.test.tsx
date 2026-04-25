import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import MarketplaceModerationPage from "./MarketplaceModerationPage";
import {
  MarketplaceModerationOfferDetailPage,
  MarketplaceModerationProductDetailPage,
  MarketplaceModerationServiceDetailPage,
} from "./MarketplaceModerationDetailPage";
import * as moderationApi from "../../api/marketplaceModeration";
import { ApiError } from "../../api/http";
import { buildAdminPermissions } from "../../admin/access";

const useAdminMock = vi.fn();

vi.mock("../../api/marketplaceModeration", () => ({
  fetchModerationQueue: vi.fn(),
  fetchModerationAudit: vi.fn(),
  fetchProductCardDetail: vi.fn(),
  fetchServiceDetail: vi.fn(),
  fetchOfferDetail: vi.fn(),
  approveMarketplaceEntity: vi.fn(),
  rejectMarketplaceEntity: vi.fn(),
}));

vi.mock("../../admin/AdminContext", () => ({
  useAdmin: () => useAdminMock(),
}));

const Wrapper: React.FC<React.PropsWithChildren> = ({ children }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe("Marketplace moderation UI", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["PLATFORM_ADMIN"]),
        read_only: false,
      },
    });
    (moderationApi.fetchModerationQueue as unknown as Mock).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });
    (moderationApi.fetchModerationAudit as unknown as Mock).mockResolvedValue({ items: [] });
  });

  it("renders the default pending-review queue empty state", async () => {
    render(
      <Wrapper>
        <MemoryRouter initialEntries={["/marketplace/moderation"]}>
          <Routes>
            <Route path="/marketplace/moderation" element={<MarketplaceModerationPage />} />
          </Routes>
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Moderation queue is empty")).toBeInTheDocument();
    expect(screen.getByText("There are no pending review items in the current moderation contour.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reset filters" })).not.toBeInTheDocument();
  });

  it("renders queue and opens detail", async () => {
    (moderationApi.fetchModerationQueue as unknown as Mock).mockResolvedValue({
      items: [
        {
          type: "PRODUCT",
          id: "prod-1",
          partner_id: "partner-1",
          title: "Product 1",
          status: "PENDING_REVIEW",
          submitted_at: "2024-06-01T10:00:00Z",
          updated_at: "2024-06-01T10:00:00Z",
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    });
    (moderationApi.fetchProductCardDetail as unknown as Mock).mockResolvedValue({
      id: "prod-1",
      partner_id: "partner-1",
      title: "Product 1",
      description: "Desc",
      category: "Category",
      status: "PENDING_REVIEW",
      tags: [],
      attributes: {},
      variants: [],
      media: [],
      created_at: "2024-06-01T09:00:00Z",
    });
    (moderationApi.fetchModerationAudit as unknown as Mock).mockResolvedValue({ items: [] });

    const user = userEvent.setup();

    render(
      <Wrapper>
        <MemoryRouter initialEntries={["/marketplace/moderation"]}>
          <Routes>
            <Route path="/marketplace/moderation" element={<MarketplaceModerationPage />} />
            <Route path="/marketplace/moderation/product/:id" element={<MarketplaceModerationProductDetailPage />} />
            <Route path="/marketplace/moderation/service/:id" element={<MarketplaceModerationServiceDetailPage />} />
            <Route path="/marketplace/moderation/offer/:id" element={<MarketplaceModerationOfferDetailPage />} />
          </Routes>
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Product 1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open" }));

    expect(await screen.findByText("Product 1")).toBeInTheDocument();
    expect(screen.getByText(/PENDING_REVIEW/)).toBeInTheDocument();
  });

  it("shows filtered-empty reset on the moderation queue and restores the row after reset", async () => {
    (moderationApi.fetchModerationQueue as unknown as Mock)
      .mockResolvedValueOnce({
        items: [
          {
            type: "PRODUCT",
            id: "prod-filter",
            partner_id: "partner-1",
            title: "Product filter",
            status: "PENDING_REVIEW",
            submitted_at: "2024-06-01T10:00:00Z",
            updated_at: "2024-06-01T10:00:00Z",
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        limit: 20,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [
          {
            type: "PRODUCT",
            id: "prod-filter",
            partner_id: "partner-1",
            title: "Product filter",
            status: "PENDING_REVIEW",
            submitted_at: "2024-06-01T10:00:00Z",
            updated_at: "2024-06-01T10:00:00Z",
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      });

    const user = userEvent.setup();

    render(
      <Wrapper>
        <MemoryRouter initialEntries={["/marketplace/moderation"]}>
          <Routes>
            <Route path="/marketplace/moderation" element={<MarketplaceModerationPage />} />
          </Routes>
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Product filter")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "missing" } });

    expect(await screen.findByText("Moderation items not found")).toBeInTheDocument();
    expect(screen.getByText("Reset filters or broaden the moderation contour.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Reset filters" }));

    expect(await screen.findByText("Product filter")).toBeInTheDocument();
  });

  it("validates reject modal", async () => {
    (moderationApi.fetchProductCardDetail as unknown as Mock).mockResolvedValue({
      id: "prod-2",
      partner_id: "partner-2",
      title: "Product 2",
      description: "Desc",
      category: "Category",
      status: "PENDING_REVIEW",
      tags: [],
      attributes: {},
      variants: [],
      media: [],
      created_at: "2024-06-01T09:00:00Z",
    });
    (moderationApi.fetchModerationAudit as unknown as Mock).mockResolvedValue({ items: [] });

    const user = userEvent.setup();

    render(
      <Wrapper>
        <MemoryRouter initialEntries={["/marketplace/moderation/product/prod-2"]}>
          <Routes>
            <Route path="/marketplace/moderation/product/:id" element={<MarketplaceModerationProductDetailPage />} />
          </Routes>
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Product 2")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Reject" }));

    const confirmButton = screen.getAllByRole("button", { name: "Reject" })[1];
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "MISSING_INFO" } });
    fireEvent.change(screen.getByPlaceholderText(/10\+ characters/), { target: { value: "Too short" } });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/10\+ characters/), { target: { value: "Missing mandatory data" } });
    expect(confirmButton).toBeEnabled();
  });

  it("renders detail empty states while keeping moderation actions available", async () => {
    (moderationApi.fetchServiceDetail as unknown as Mock).mockResolvedValue({
      id: "svc-1",
      partner_id: "partner-4",
      title: "Service 1",
      description: "",
      duration_min: 45,
      requirements: "",
      status: "PENDING_REVIEW",
      locations: [],
      schedule: null,
      media: [],
      created_at: "2024-06-01T09:00:00Z",
    });
    (moderationApi.fetchModerationAudit as unknown as Mock).mockResolvedValue({ items: [] });

    render(
      <Wrapper>
        <MemoryRouter initialEntries={["/marketplace/moderation/service/svc-1"]}>
          <Routes>
            <Route path="/marketplace/moderation/service/:id" element={<MarketplaceModerationServiceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Service 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
    expect(screen.getByText("No moderation events yet")).toBeInTheDocument();
    expect(screen.getByText("No locations linked")).toBeInTheDocument();
    expect(screen.getByText("No schedule preview")).toBeInTheDocument();
    expect(screen.getAllByText("No media attached").length).toBeGreaterThan(0);
  });

  it("renders moderation details as read-only when role lacks approve capability", async () => {
    useAdminMock.mockReturnValue({
      profile: {
        permissions: buildAdminPermissions(["NEFT_SUPPORT"]),
        read_only: false,
      },
    });
    (moderationApi.fetchProductCardDetail as unknown as Mock).mockResolvedValue({
      id: "prod-readonly",
      partner_id: "partner-5",
      title: "Read-only Product",
      description: "Desc",
      category: "Category",
      status: "PENDING_REVIEW",
      tags: [],
      attributes: {},
      variants: [],
      media: [],
      created_at: "2024-06-01T09:00:00Z",
    });
    (moderationApi.fetchModerationAudit as unknown as Mock).mockResolvedValue({ items: [] });

    render(
      <Wrapper>
        <MemoryRouter initialEntries={["/marketplace/moderation/product/prod-readonly"]}>
          <Routes>
            <Route path="/marketplace/moderation/product/:id" element={<MarketplaceModerationProductDetailPage />} />
          </Routes>
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Read-only Product")).toBeInTheDocument();
    expect(screen.getByText("Read-only moderation")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
  });

  it("approves entity and refreshes status", async () => {
    (moderationApi.fetchProductCardDetail as unknown as Mock)
      .mockResolvedValueOnce({
        id: "prod-3",
        partner_id: "partner-3",
        title: "Product 3",
        description: "Desc",
        category: "Category",
        status: "PENDING_REVIEW",
        tags: [],
        attributes: {},
        variants: [],
        media: [],
        created_at: "2024-06-01T09:00:00Z",
      })
      .mockResolvedValueOnce({
        id: "prod-3",
        partner_id: "partner-3",
        title: "Product 3",
        description: "Desc",
        category: "Category",
        status: "ACTIVE",
        tags: [],
        attributes: {},
        variants: [],
        media: [],
        created_at: "2024-06-01T09:00:00Z",
      });
    (moderationApi.fetchModerationAudit as unknown as Mock).mockResolvedValue({ items: [] });
    (moderationApi.approveMarketplaceEntity as unknown as Mock).mockResolvedValue({});

    const user = userEvent.setup();

    render(
      <Wrapper>
        <MemoryRouter initialEntries={["/marketplace/moderation/product/prod-3"]}>
          <Routes>
            <Route path="/marketplace/moderation/product/:id" element={<MarketplaceModerationProductDetailPage />} />
          </Routes>
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Product 3")).toBeInTheDocument();
    expect(screen.getByText(/PENDING_REVIEW/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(moderationApi.approveMarketplaceEntity).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText(/ACTIVE/)).toBeInTheDocument());
  });

  it("renders structured moderation detail error metadata without using a raw payload as the primary message", async () => {
    (moderationApi.fetchProductCardDetail as unknown as Mock).mockRejectedValue(
      new ApiError(
        JSON.stringify({
          error: "admin_internal_error",
          message: "Internal Server Error",
          request_id: "req-moderation-1",
        }),
        500,
        "req-moderation-1",
        "corr-moderation-1",
        "admin_internal_error",
      ),
    );

    render(
      <Wrapper>
        <MemoryRouter initialEntries={["/marketplace/moderation/product/prod-error"]}>
          <Routes>
            <Route path="/marketplace/moderation/product/:id" element={<MarketplaceModerationProductDetailPage />} />
          </Routes>
        </MemoryRouter>
      </Wrapper>,
    );

    expect(await screen.findByText("Failed to load moderation detail")).toBeInTheDocument();
    expect(screen.getByText("Moderation detail owner route returned an internal error. Retry or inspect request metadata below.")).toBeInTheDocument();
    expect(screen.getByText(/request_id: req-moderation-1/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

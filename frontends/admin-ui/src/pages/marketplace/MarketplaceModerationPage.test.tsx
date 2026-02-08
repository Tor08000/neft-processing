import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

vi.mock("../../api/marketplaceModeration", () => ({
  fetchModerationQueue: vi.fn(),
  fetchModerationAudit: vi.fn(),
  fetchProductCardDetail: vi.fn(),
  fetchServiceDetail: vi.fn(),
  fetchOfferDetail: vi.fn(),
  approveMarketplaceEntity: vi.fn(),
  rejectMarketplaceEntity: vi.fn(),
}));

const Wrapper: React.FC<React.PropsWithChildren> = ({ children }) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

describe("Marketplace moderation UI", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    (moderationApi.fetchModerationQueue as unknown as Mock).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });
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

    await user.selectOptions(screen.getByRole("combobox"), "MISSING_INFO");
    await user.type(screen.getByPlaceholderText(/10\+ символов/), "Too short");
    expect(confirmButton).toBeDisabled();

    await user.clear(screen.getByPlaceholderText(/10\+ символов/));
    await user.type(screen.getByPlaceholderText(/10\+ символов/), "Missing mandatory data");
    expect(confirmButton).toBeEnabled();
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
});

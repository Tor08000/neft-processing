import { apiGet, apiPost } from "./client";
import type {
  MarketplaceModerationQueueResponse,
  MarketplaceModerationStatus,
  MarketplaceModerationProduct,
} from "../types/marketplaceModeration";

export async function fetchModerationQueue(params: {
  status?: MarketplaceModerationStatus;
  limit?: number;
  offset?: number;
}): Promise<MarketplaceModerationQueueResponse> {
  return apiGet("/api/core/v1/admin/marketplace/moderation/queue", params);
}

export async function approveMarketplaceProduct(productId: string): Promise<MarketplaceModerationProduct> {
  return apiPost(`/api/core/v1/admin/marketplace/moderation/${productId}/approve`);
}

export async function rejectMarketplaceProduct(productId: string, reason: string): Promise<MarketplaceModerationProduct> {
  return apiPost(`/api/core/v1/admin/marketplace/moderation/${productId}/reject`, { reason });
}

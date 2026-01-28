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
  return apiGet("/marketplace/moderation/queue", params);
}

export async function approveMarketplaceProduct(productId: string): Promise<MarketplaceModerationProduct> {
  return apiPost(`/marketplace/moderation/${productId}/approve`);
}

export async function rejectMarketplaceProduct(productId: string, reason: string): Promise<MarketplaceModerationProduct> {
  return apiPost(`/marketplace/moderation/${productId}/reject`, { reason });
}

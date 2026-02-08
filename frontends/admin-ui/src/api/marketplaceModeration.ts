import { apiGet, apiPost } from "./client";
import type {
  MarketplaceModerationAuditResponse,
  MarketplaceModerationEntityType,
  MarketplaceModerationQueueResponse,
  MarketplaceModerationReasonCode,
  MarketplaceModerationStatus,
  MarketplaceOfferDetail,
  MarketplaceProductCardDetail,
  MarketplaceServiceDetail,
} from "../types/marketplaceModeration";

export async function fetchModerationQueue(params: {
  type?: MarketplaceModerationEntityType;
  status?: MarketplaceModerationStatus;
  limit?: number;
  offset?: number;
  q?: string;
}): Promise<MarketplaceModerationQueueResponse> {
  return apiGet("/marketplace/moderation/queue", params);
}

export async function fetchModerationAudit(params: {
  type: MarketplaceModerationEntityType;
  id: string;
}): Promise<MarketplaceModerationAuditResponse> {
  return apiGet("/marketplace/moderation/audit", params);
}

export async function fetchProductCardDetail(productId: string): Promise<MarketplaceProductCardDetail> {
  return apiGet(`/marketplace/products/${productId}`);
}

export async function fetchServiceDetail(serviceId: string): Promise<MarketplaceServiceDetail> {
  return apiGet(`/marketplace/services/${serviceId}`);
}

export async function fetchOfferDetail(offerId: string): Promise<MarketplaceOfferDetail> {
  return apiGet(`/marketplace/offers/${offerId}`);
}

export async function approveMarketplaceEntity(type: MarketplaceModerationEntityType, id: string): Promise<unknown> {
  switch (type) {
    case "PRODUCT":
      return apiPost(`/marketplace/products/${id}:approve`);
    case "SERVICE":
      return apiPost(`/marketplace/services/${id}:approve`);
    case "OFFER":
      return apiPost(`/marketplace/offers/${id}:approve`);
    default:
      throw new Error("Unsupported moderation type");
  }
}

export async function rejectMarketplaceEntity(
  type: MarketplaceModerationEntityType,
  id: string,
  payload: { reason_code: MarketplaceModerationReasonCode; comment: string },
): Promise<unknown> {
  switch (type) {
    case "PRODUCT":
      return apiPost(`/marketplace/products/${id}:reject`, payload);
    case "SERVICE":
      return apiPost(`/marketplace/services/${id}:reject`, payload);
    case "OFFER":
      return apiPost(`/marketplace/offers/${id}:reject`, payload);
    default:
      throw new Error("Unsupported moderation type");
  }
}

import { request } from "./http";
import type {
  MarketplaceService,
  MarketplaceServiceAvailabilityResponse,
  MarketplaceServiceListResponse,
  MarketplaceServiceLocation,
  MarketplaceServiceMedia,
  MarketplaceServiceSchedule,
  MarketplaceServiceScheduleException,
  MarketplaceServiceScheduleRule,
  MarketplaceServiceInput,
  MarketplaceServiceUpdate,
} from "../types/marketplace";

const withToken = (token: string | null | undefined) => ({ token: token ?? undefined, base: "core_root" as const });

export interface MarketplaceServiceFilters {
  status?: string;
  q?: string;
  category?: string;
  limit?: string;
  offset?: string;
}

const toQuery = (filters: MarketplaceServiceFilters): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchMarketplaceServices = (token: string | null | undefined, filters: MarketplaceServiceFilters = {}) =>
  request<MarketplaceServiceListResponse>(`/partner/services${toQuery(filters)}`, {}, withToken(token));

export const fetchMarketplaceService = (token: string | null | undefined, id: string) =>
  request<MarketplaceService>(`/partner/services/${id}`, {}, withToken(token));

export const createMarketplaceService = (token: string | null | undefined, payload: MarketplaceServiceInput) =>
  request<MarketplaceService>("/partner/services", { method: "POST", body: JSON.stringify(payload) }, withToken(token));

export const updateMarketplaceService = (
  token: string | null | undefined,
  id: string,
  payload: MarketplaceServiceUpdate,
) =>
  request<MarketplaceService>(
    `/partner/services/${id}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    withToken(token),
  );

export const submitMarketplaceService = (token: string | null | undefined, id: string) =>
  request<MarketplaceService>(`/partner/services/${id}/submit`, { method: "POST" }, withToken(token));

export const archiveMarketplaceService = (token: string | null | undefined, id: string) =>
  request<MarketplaceService>(`/partner/services/${id}/archive`, { method: "POST" }, withToken(token));

export const addMarketplaceServiceMedia = (
  token: string | null | undefined,
  serviceId: string,
  payload: MarketplaceServiceMedia,
) =>
  request<MarketplaceServiceMedia>(
    `/partner/services/${serviceId}/media`,
    { method: "POST", body: JSON.stringify(payload) },
    withToken(token),
  );

export const removeMarketplaceServiceMedia = (
  token: string | null | undefined,
  serviceId: string,
  attachmentId: string,
) =>
  request<void>(
    `/partner/services/${serviceId}/media/${attachmentId}`,
    { method: "DELETE" },
    withToken(token),
  );

export const fetchMarketplaceServiceLocations = (token: string | null | undefined, serviceId: string) =>
  request<MarketplaceServiceLocation[]>(`/partner/services/${serviceId}/locations`, {}, withToken(token));

export const addMarketplaceServiceLocation = (
  token: string | null | undefined,
  serviceId: string,
  payload: { location_id: string; is_active?: boolean },
) =>
  request<MarketplaceServiceLocation>(
    `/partner/services/${serviceId}/locations`,
    { method: "POST", body: JSON.stringify(payload) },
    withToken(token),
  );

export const removeMarketplaceServiceLocation = (
  token: string | null | undefined,
  serviceId: string,
  serviceLocationId: string,
) =>
  request<void>(
    `/partner/services/${serviceId}/locations/${serviceLocationId}`,
    { method: "DELETE" },
    withToken(token),
  );

export const fetchMarketplaceServiceSchedule = (token: string | null | undefined, serviceLocationId: string) =>
  request<MarketplaceServiceSchedule>(
    `/partner/service-locations/${serviceLocationId}/schedule`,
    {},
    withToken(token),
  );

export const addMarketplaceServiceScheduleRule = (
  token: string | null | undefined,
  serviceLocationId: string,
  payload: Omit<MarketplaceServiceScheduleRule, "id" | "service_location_id" | "created_at">,
) =>
  request<MarketplaceServiceScheduleRule>(
    `/partner/service-locations/${serviceLocationId}/schedule/rules`,
    { method: "POST", body: JSON.stringify(payload) },
    withToken(token),
  );

export const removeMarketplaceServiceScheduleRule = (
  token: string | null | undefined,
  serviceLocationId: string,
  ruleId: string,
) =>
  request<void>(
    `/partner/service-locations/${serviceLocationId}/schedule/rules/${ruleId}`,
    { method: "DELETE" },
    withToken(token),
  );

export const addMarketplaceServiceScheduleException = (
  token: string | null | undefined,
  serviceLocationId: string,
  payload: Omit<MarketplaceServiceScheduleException, "id" | "service_location_id" | "created_at">,
) =>
  request<MarketplaceServiceScheduleException>(
    `/partner/service-locations/${serviceLocationId}/schedule/exceptions`,
    { method: "POST", body: JSON.stringify(payload) },
    withToken(token),
  );

export const removeMarketplaceServiceScheduleException = (
  token: string | null | undefined,
  serviceLocationId: string,
  exceptionId: string,
) =>
  request<void>(
    `/partner/service-locations/${serviceLocationId}/schedule/exceptions/${exceptionId}`,
    { method: "DELETE" },
    withToken(token),
  );

export const fetchMarketplaceServiceAvailability = (
  token: string | null | undefined,
  serviceId: string,
  dateFrom?: string,
  dateTo?: string,
) => {
  const params = new URLSearchParams();
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const query = params.toString();
  return request<MarketplaceServiceAvailabilityResponse>(
    `/partner/services/${serviceId}/availability${query ? `?${query}` : ""}`,
    {},
    withToken(token),
  );
};

import { request } from "./http";
import type { AuthSession } from "./types";
import type { OperationDetails, OperationsPage } from "../types/operations";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

interface OperationFilters {
  status?: string;
  cardId?: string;
  from?: string;
  to?: string;
  merchantId?: string;
  productType?: string;
  vehicleId?: string;
  driverId?: string;
  minAmount?: string;
  maxAmount?: string;
  limit?: number;
  offset?: number;
}

export function fetchOperations(user: AuthSession | null, filters: OperationFilters = {}): Promise<OperationsPage> {
  const search = new URLSearchParams();
  if (filters.status) search.set("status", filters.status);
  if (filters.cardId) search.set("card_id", filters.cardId);
  if (filters.from) search.set("from", filters.from);
  if (filters.to) search.set("to", filters.to);
  if (filters.merchantId) search.set("merchant_id", filters.merchantId);
  if (filters.productType) search.set("product_type", filters.productType);
  if (filters.vehicleId) search.set("vehicle_id", filters.vehicleId);
  if (filters.driverId) search.set("driver_id", filters.driverId);
  if (filters.minAmount) search.set("min_amount", filters.minAmount);
  if (filters.maxAmount) search.set("max_amount", filters.maxAmount);
  if (filters.limit) search.set("limit", filters.limit.toString());
  if (filters.offset) search.set("offset", filters.offset.toString());

  const query = search.toString();
  const path = query ? `/operations?${query}` : "/operations";
  return request<OperationsPage>(path, { method: "GET" }, withToken(user));
}

export function fetchOperationDetails(id: string, user: AuthSession | null): Promise<OperationDetails> {
  return request<OperationDetails>(`/operations/${id}`, { method: "GET" }, withToken(user));
}

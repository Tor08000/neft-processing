import { request } from "./http";
import { RevenueOverdueResponse, RevenueSummaryResponse } from "../types/revenue";

export const fetchRevenueSummary = async (asOf: string, token?: string | null): Promise<RevenueSummaryResponse> => {
  return request<RevenueSummaryResponse>(`/revenue/summary?as_of=${asOf}`, {}, token);
};

export type OverdueBucket = "all" | "0_7" | "8_30" | "31_90" | "90_plus";

export const fetchOverdueList = async (
  params: { bucket: OverdueBucket; limit: number; offset: number; asOf: string },
  token?: string | null,
): Promise<RevenueOverdueResponse> => {
  const query = new URLSearchParams({
    bucket: params.bucket,
    limit: String(params.limit),
    offset: String(params.offset),
    as_of: params.asOf,
  });
  return request<RevenueOverdueResponse>(`/revenue/overdue?${query.toString()}`, {}, token);
};

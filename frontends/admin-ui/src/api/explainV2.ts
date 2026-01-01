import { apiGet, apiPost } from "./client";
import type {
  ExplainActionCatalogItem,
  ExplainDiffResponse,
  ExplainV2Response,
  WhatIfEvaluateRequest,
  WhatIfResponse,
} from "../types/explainV2";

export const fetchExplainV2 = async (params: Record<string, string | number | undefined>): Promise<ExplainV2Response> => {
  return apiGet("/explain", params);
};

export const fetchExplainActions = async (
  params: Record<string, string | number | undefined>,
): Promise<ExplainActionCatalogItem[]> => {
  return apiGet("/explain/actions", params);
};

export const evaluateWhatIf = async (payload: WhatIfEvaluateRequest): Promise<WhatIfResponse> => {
  return apiPost("/v1/admin/what-if/evaluate", payload);
};

export const fetchExplainDiff = async (payload: {
  context: { kind: "operation" | "invoice" | "order" | "kpi"; id: string };
  actions: { code: string }[];
}): Promise<ExplainDiffResponse> => {
  return apiPost("/explain/diff", payload);
};

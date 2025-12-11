import { apiGet, apiPost, apiPut } from "./client";
import {
  type RiskRule,
  type RiskRuleListResponse,
  type RiskRulePayload,
  type RiskRulesQuery,
} from "../types/riskRules";

export async function fetchRiskRules(params?: RiskRulesQuery): Promise<RiskRuleListResponse> {
  return apiGet("/api/v1/admin/risk/rules", params);
}

export async function fetchRiskRule(id: number | string): Promise<RiskRule> {
  return apiGet(`/api/v1/admin/risk/rules/${id}`);
}

export async function createRiskRule(payload: RiskRulePayload): Promise<RiskRule> {
  return apiPost("/api/v1/admin/risk/rules", payload);
}

export async function updateRiskRule(
  id: number | string,
  payload: RiskRulePayload,
): Promise<RiskRule> {
  return apiPut(`/api/v1/admin/risk/rules/${id}`);
}

export async function enableRiskRule(id: number | string): Promise<RiskRule> {
  return apiPost(`/api/v1/admin/risk/rules/${id}/enable`);
}

export async function disableRiskRule(id: number | string): Promise<RiskRule> {
  return apiPost(`/api/v1/admin/risk/rules/${id}/disable`);
}

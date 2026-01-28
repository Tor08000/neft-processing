import { apiGet } from "./client";
import type {
  OpsBlockedPayoutsResponse,
  OpsFailedExportsResponse,
  OpsFailedImportsResponse,
  OpsSupportBreachesResponse,
  OpsSummaryResponse,
} from "../types/ops";

export const fetchOpsSummary = () => apiGet<OpsSummaryResponse>("/ops/summary");

export const fetchOpsBlockedPayouts = (limit = 50) =>
  apiGet<OpsBlockedPayoutsResponse>("/ops/payouts/blocked", { limit });

export const fetchOpsFailedExports = (limit = 50) =>
  apiGet<OpsFailedExportsResponse>("/ops/exports/failed", { limit });

export const fetchOpsFailedImports = (limit = 50) =>
  apiGet<OpsFailedImportsResponse>("/ops/reconciliation/failed", { limit });

export const fetchOpsSupportBreaches = (limit = 50) =>
  apiGet<OpsSupportBreachesResponse>("/ops/support/breaches", { limit });

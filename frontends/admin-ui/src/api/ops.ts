import { apiGet } from "./client";
import type {
  OpsBlockedPayoutsResponse,
  OpsFailedExportsResponse,
  OpsFailedImportsResponse,
  OpsSupportBreachesResponse,
  OpsSummaryResponse,
} from "../types/ops";

export const fetchOpsSummary = () => apiGet<OpsSummaryResponse>("/api/core/v1/admin/ops/summary");

export const fetchOpsBlockedPayouts = (limit = 50) =>
  apiGet<OpsBlockedPayoutsResponse>("/api/core/v1/admin/ops/payouts/blocked", { limit });

export const fetchOpsFailedExports = (limit = 50) =>
  apiGet<OpsFailedExportsResponse>("/api/core/v1/admin/ops/exports/failed", { limit });

export const fetchOpsFailedImports = (limit = 50) =>
  apiGet<OpsFailedImportsResponse>("/api/core/v1/admin/ops/reconciliation/failed", { limit });

export const fetchOpsSupportBreaches = (limit = 50) =>
  apiGet<OpsSupportBreachesResponse>("/api/core/v1/admin/ops/support/breaches", { limit });

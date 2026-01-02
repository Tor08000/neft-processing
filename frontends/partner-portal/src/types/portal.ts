export interface PortalSlaSummary {
  status: string;
  violations: number;
}

export interface PartnerDashboardSummary {
  active_contracts: number;
  current_settlement_period?: string | null;
  upcoming_payout?: number | null;
  sla_score?: number | null;
  sla: PortalSlaSummary;
}

export interface PartnerContractSummary {
  contract_number: string;
  contract_type: string;
  effective_from: string;
  effective_to?: string | null;
  status: string;
  sla_status: string;
  sla_violations: number;
}

export interface PartnerContractsResponse {
  items: PartnerContractSummary[];
}

export interface PartnerSettlementSummary {
  settlement_ref: string;
  period_start: string;
  period_end: string;
  gross: number;
  fees: number;
  refunds: number;
  net_amount: number;
  status: string;
  currency: string;
}

export interface PartnerSettlementItemSummary {
  source_type: string;
  direction: string;
  count: number;
  amount: number;
}

export interface PartnerSettlementDetails extends PartnerSettlementSummary {
  items_summary: PartnerSettlementItemSummary[];
  payout_status?: string | null;
}

export interface PartnerSettlementListResponse {
  items: PartnerSettlementSummary[];
}

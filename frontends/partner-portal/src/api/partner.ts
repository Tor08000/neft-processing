import { request } from "./http";

export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export interface PartnerProfile {
  id: string;
  name: string;
  legalName?: string | null;
  inn?: string | null;
  kpp?: string | null;
  contactEmail?: string | null;
  settlementAccount?: string | null;
}

export interface StationListItem {
  id: string;
  name: string;
  code?: string | null;
  network?: string | null;
  address: string;
  status: "active" | "inactive";
  onlineStatus?: "online" | "offline" | null;
  transactionsCount?: number | null;
}

export interface StationDetail extends StationListItem {
  terminals?: Terminal[];
  transactionSummary?: StationTransactionSummary;
  declineReasons?: DeclineReason[];
  prices?: StationPrice[];
}

export interface Terminal {
  id: string;
  name?: string | null;
  status: "active" | "inactive" | "offline";
}

export interface StationTransactionSummary {
  totalAmount?: number | null;
  totalCount?: number | null;
  period?: string | null;
}

export interface DeclineReason {
  code: string;
  label: string;
  count: number;
  explainUrl?: string | null;
}

export interface StationPrice {
  product: string;
  price: number;
  updatedAt?: string | null;
}

export interface TransactionListItem {
  id: string;
  ts: string;
  station: string;
  product: string;
  quantity?: number | null;
  amount: number;
  status: "authorized" | "declined" | "settled";
  primaryReason?: string | null;
  explainUrl?: string | null;
}

export interface TransactionDetail extends TransactionListItem {
  terminalId?: string | null;
  cardMasked?: string | null;
  moneyFlowUrl?: string | null;
}

export interface SettlementListItem {
  id: string;
  periodStart: string;
  periodEnd: string;
  grossAmount: number;
  netAmount: number;
  status: "draft" | "queued" | "sent" | "settled";
  transactionsCount?: number | null;
}

export interface SettlementDetail extends SettlementListItem {
  breakdowns?: SettlementBreakdown[];
  commissions?: SettlementCommission[];
  payoutBatches?: PayoutBatch[];
  documents?: SettlementDocumentLink[];
  edoStatus?: string | null;
}

export interface SettlementBreakdown {
  station: string;
  product: string;
  amount: number;
  count?: number | null;
}

export interface SettlementCommission {
  label: string;
  amount: number;
}

export interface SettlementDocumentLink {
  id: string;
  type: string;
  status: string;
}

export interface PayoutBatch {
  id: string;
  status: "draft" | "sent" | "settled" | "failed";
  exportFiles?: ExportFile[];
  checksum?: string | null;
  auditSummary?: string | null;
}

export interface ExportFile {
  id: string;
  name: string;
  url?: string | null;
  checksum?: string | null;
}

export interface PartnerDocumentListItem {
  id: string;
  type: string;
  period: string;
  amount?: number | null;
  status: string;
  signatureStatus?: string | null;
  edoStatus?: string | null;
}

export interface PartnerDocumentDetail extends PartnerDocumentListItem {
  files?: PartnerDocumentFile[];
  signatures?: DocumentSignature[];
  edoEvents?: EdoEvent[];
}

export interface PartnerDocumentFile {
  id: string;
  name: string;
  url?: string | null;
}

export interface DocumentSignature {
  signer: string;
  status: string;
  signedAt?: string | null;
}

export interface EdoEvent {
  id: string;
  status: string;
  timestamp: string;
  description?: string | null;
}

export interface ServiceCatalogItem {
  id: string;
  name: string;
  status: "active" | "draft";
  price?: number | null;
}

export interface PartnerUser {
  id: string;
  email: string;
  role: string;
}

export interface IntegrationSetting {
  name: string;
  value: string;
}

export interface PartnerSettings {
  profile: PartnerProfile;
  integrations: IntegrationSetting[];
  users: PartnerUser[];
}

export interface TransactionFilters {
  periodStart?: string;
  periodEnd?: string;
  stationId?: string;
  productType?: string;
  status?: string;
  amountMin?: string;
  amountMax?: string;
}

const toQuery = (filters: Record<string, string | undefined>): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchPartnerProfile = (token: string) => request<PartnerProfile>("/partner/profile", {}, token);

export const fetchStations = (token: string) => request<PaginatedResponse<StationListItem>>("/partner/stations", {}, token);

export const fetchStationDetail = (token: string, stationId: string) =>
  request<StationDetail>(`/partner/stations/${stationId}`, {}, token);

export const fetchTransactions = (token: string, filters: TransactionFilters) =>
  request<PaginatedResponse<TransactionListItem>>(`/partner/transactions${toQuery(filters)}`, {}, token);

export const fetchTransactionDetail = (token: string, transactionId: string) =>
  request<TransactionDetail>(`/partner/transactions/${transactionId}`, {}, token);

export const fetchSettlements = (token: string) =>
  request<PaginatedResponse<SettlementListItem>>("/partner/settlements", {}, token);

export const fetchSettlementDetail = (token: string, settlementId: string) =>
  request<SettlementDetail>(`/partner/settlements/${settlementId}`, {}, token);

export const fetchPayoutBatches = (token: string) =>
  request<PaginatedResponse<PayoutBatch>>("/partner/payout-batches", {}, token);

export const fetchDocuments = (token: string) =>
  request<PaginatedResponse<PartnerDocumentListItem>>("/partner/documents", {}, token);

export const fetchDocumentDetail = (token: string, documentId: string) =>
  request<PartnerDocumentDetail>(`/partner/documents/${documentId}`, {}, token);

export const fetchServices = (token: string) =>
  request<PaginatedResponse<ServiceCatalogItem>>("/partner/services", {}, token);

export const fetchSettings = (token: string) => request<PartnerSettings>("/partner/settings", {}, token);

export const confirmSettlementReceived = (token: string, settlementId: string) =>
  request(`/partner/settlements/${settlementId}/confirm`, { method: "POST" }, token);

export const requestReconciliation = (token: string, settlementId: string) =>
  request(`/partner/settlements/${settlementId}/reconciliation-requests`, { method: "POST" }, token);

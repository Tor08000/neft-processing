import { request, requestFormData } from "./http";

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


export interface FuelStationPriceItem {
  product_code: string;
  price: number;
  currency?: string | null;
  valid_from?: string | null;
  valid_to?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
}

export interface FuelStationPricesResponse {
  station_id: string;
  as_of?: string | null;
  currency?: string | null;
  items: FuelStationPriceItem[];
}

export interface FuelStationPricesUpsertPayload {
  source: "MANUAL";
  items: Array<{
    product_code: string;
    price: number;
    currency: string;
    valid_from?: string | null;
    valid_to?: string | null;
  }>;
}

export interface FuelStationPriceImportError {
  row: number;
  error: string;
  raw?: string | null;
}

export interface FuelStationPriceImportSummary {
  station_id: string;
  inserted: number;
  updated: number;
  skipped: number;
  errors: FuelStationPriceImportError[];
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
  [key: string]: string | undefined;
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


export const fetchFuelStationPrices = (token: string, stationId: string) =>
  request<FuelStationPricesResponse>(`/api/v1/fuel/stations/${stationId}/prices`, { method: "GET" }, { token, base: "core_root" });

export const saveFuelStationPrices = (token: string, stationId: string, payload: FuelStationPricesUpsertPayload) =>
  request<FuelStationPricesResponse>(
    `/api/v1/partner/fuel/stations/${stationId}/prices`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    { token, base: "core_root" },
  );

export const importFuelStationPrices = (token: string, stationId: string, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return requestFormData<FuelStationPriceImportSummary>(
    `/api/v1/partner/fuel/stations/${stationId}/prices/import`,
    formData,
    { token, base: "core_root" },
  );
};

export interface PartnerMeV1Response {
  partner: {
    id: string;
    code: string;
    legal_name: string;
    brand_name?: string | null;
    status: string;
    contacts?: Record<string, unknown>;
  };
  my_roles: string[];
}

export interface PartnerLocationV1 {
  id: string;
  partner_id: string;
  title: string;
  address: string;
  city?: string | null;
  region?: string | null;
  external_id?: string | null;
  code?: string | null;
  lat?: number | null;
  lon?: number | null;
  status: string;
}

export interface PartnerTermsV1 {
  id: string;
  partner_id: string;
  version: number;
  status: string;
  terms: Record<string, unknown>;
}

export const fetchPartnerMeV1 = (token: string) => request<PartnerMeV1Response>("/partner/me", {}, token);
export const patchPartnerMeV1 = (token: string, payload: { brand_name?: string; contacts?: Record<string, unknown> }) =>
  request<PartnerProfile>("/partner/me", { method: "PATCH", body: JSON.stringify(payload) }, token);
export const fetchPartnerLocationsV1 = (token: string) => request<PartnerLocationV1[]>("/partner/locations", {}, token);
export const createPartnerLocationV1 = (
  token: string,
  payload: { title: string; address: string; city?: string; region?: string; external_id?: string; lat?: number; lon?: number },
) => request<PartnerLocationV1>("/partner/locations", { method: "POST", body: JSON.stringify(payload) }, token);
export const patchPartnerLocationV1 = (token: string, id: string, payload: Partial<PartnerLocationV1>) =>
  request<PartnerLocationV1>(`/partner/locations/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
export const deactivatePartnerLocationV1 = (token: string, id: string) =>
  request<PartnerLocationV1>(`/partner/locations/${id}`, { method: "DELETE" }, token);
export const fetchPartnerUsersV1 = (token: string) => request<{ user_id: string; roles: string[] }[]>("/partner/users", {}, token);
export const addPartnerUserV1 = (token: string, payload: { user_id?: string; email?: string; roles: string[] }) =>
  request<{ user_id: string; roles: string[] }>("/partner/users", { method: "POST", body: JSON.stringify(payload) }, token);
export const removePartnerUserV1 = (token: string, userId: string) =>
  request(`/partner/users/${userId}`, { method: "DELETE" }, token);
export const fetchPartnerTermsV1 = (token: string) => request<PartnerTermsV1>("/partner/terms", {}, token);

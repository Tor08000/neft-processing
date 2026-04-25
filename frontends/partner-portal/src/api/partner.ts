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

export interface ExportFile {
  id: string;
  name: string;
  url?: string | null;
  checksum?: string | null;
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

export const fetchServices = (token: string) =>
  request<PaginatedResponse<ServiceCatalogItem>>("/partner/services", {}, token);

export const fetchSettings = (token: string) => request<PartnerSettings>("/partner/settings", {}, token);

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
    partner_type?: string | null;
    inn?: string | null;
    ogrn?: string | null;
    status: string;
    contacts?: Record<string, unknown>;
  };
  my_roles: string[];
}

export type PartnerSelfProfileV1 = PartnerMeV1Response["partner"];

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
  created_at: string;
  updated_at: string;
}

export interface PartnerUserRoleV1 {
  user_id: string;
  roles: string[];
  created_at: string;
}

export const fetchPartnerMeV1 = (token: string) => request<PartnerMeV1Response>("/partner/self-profile", {}, token);
export const patchPartnerMeV1 = (token: string, payload: { brand_name?: string; contacts?: Record<string, unknown> }) =>
  request<PartnerSelfProfileV1>("/partner/self-profile", { method: "PATCH", body: JSON.stringify(payload) }, token);
export const fetchPartnerLocationsV1 = (token: string) => request<PartnerLocationV1[]>("/partner/locations", {}, token);
export const createPartnerLocationV1 = (
  token: string,
  payload: { title: string; address: string; city?: string; region?: string; external_id?: string; lat?: number; lon?: number },
) => request<PartnerLocationV1>("/partner/locations", { method: "POST", body: JSON.stringify(payload) }, token);
export const patchPartnerLocationV1 = (token: string, id: string, payload: Partial<PartnerLocationV1>) =>
  request<PartnerLocationV1>(`/partner/locations/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
export const deactivatePartnerLocationV1 = (token: string, id: string) =>
  request<PartnerLocationV1>(`/partner/locations/${id}`, { method: "DELETE" }, token);
export const fetchPartnerUsersV1 = (token: string) => request<PartnerUserRoleV1[]>("/partner/users", {}, token);
export const addPartnerUserV1 = (token: string, payload: { user_id?: string; email?: string; roles: string[] }) =>
  request<PartnerUserRoleV1>("/partner/users", { method: "POST", body: JSON.stringify(payload) }, token);
export const removePartnerUserV1 = (token: string, userId: string) =>
  request(`/partner/users/${userId}`, { method: "DELETE" }, token);
export const fetchPartnerTermsV1 = (token: string) => request<PartnerTermsV1>("/partner/terms", {}, token);

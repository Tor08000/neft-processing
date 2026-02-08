import type { ProductStatus } from "../components/StatusBadge";

export type MarketplaceProductStatus = ProductStatus;
export type MarketplaceVerificationStatus = "PENDING" | "VERIFIED" | "REJECTED";
export type MarketplaceServiceStatus = ProductStatus;

export interface MarketplaceProductMedia {
  attachment_id: string;
  bucket: string;
  path: string;
  checksum?: string | null;
  size?: number | null;
  mime?: string | null;
  sort_index?: number | null;
  created_at?: string | null;
}

export interface MarketplacePartnerProfile {
  id: string;
  partner_id: string;
  company_name: string;
  description?: string | null;
  verification_status: MarketplaceVerificationStatus;
  rating?: number | null;
  created_at: string;
  updated_at?: string | null;
}

export interface MarketplaceProductSummary {
  id: string;
  partner_id: string;
  title: string;
  category: string;
  status: MarketplaceProductStatus;
  updated_at?: string | null;
  created_at?: string | null;
}

export interface MarketplaceProduct extends MarketplaceProductSummary {
  description: string;
  tags: string[];
  attributes: Record<string, string | number | boolean | null>;
  variants: Array<Record<string, unknown>>;
  media: MarketplaceProductMedia[];
}

export interface MarketplaceProductInput {
  title: string;
  description: string;
  category: string;
  tags: string[];
  attributes: Record<string, string | number | boolean | null>;
  variants: Array<Record<string, unknown>>;
}

export interface MarketplaceProductUpdate {
  title?: string;
  description?: string;
  category?: string;
  tags?: string[];
  attributes?: Record<string, string | number | boolean | null>;
  variants?: Array<Record<string, unknown>>;
}

export interface MarketplaceProductListResponse {
  items: MarketplaceProductSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface MarketplaceServiceMedia {
  attachment_id: string;
  bucket: string;
  path: string;
  checksum?: string | null;
  size?: number | null;
  mime?: string | null;
  sort_index?: number | null;
  created_at?: string | null;
}

export interface MarketplaceServiceSummary {
  id: string;
  partner_id: string;
  title: string;
  category: string;
  status: MarketplaceServiceStatus;
  duration_min: number;
  updated_at?: string | null;
  created_at?: string | null;
}

export interface MarketplaceService extends MarketplaceServiceSummary {
  description?: string | null;
  tags: string[];
  attributes: Record<string, string | number | boolean | null>;
  requirements?: string | null;
  media: MarketplaceServiceMedia[];
}

export interface MarketplaceServiceInput {
  title: string;
  description?: string | null;
  category: string;
  tags?: string[];
  attributes?: Record<string, string | number | boolean | null>;
  duration_min: number;
  requirements?: string | null;
}

export interface MarketplaceServiceUpdate {
  title?: string;
  description?: string | null;
  category?: string;
  tags?: string[];
  attributes?: Record<string, string | number | boolean | null>;
  duration_min?: number;
  requirements?: string | null;
}

export interface MarketplaceServiceListResponse {
  items: MarketplaceServiceSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface MarketplaceServiceLocation {
  id: string;
  service_id: string;
  location_id: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  is_active: boolean;
  created_at?: string | null;
}

export interface MarketplaceServiceScheduleRule {
  id: string;
  service_location_id: string;
  weekday: number;
  time_from: string;
  time_to: string;
  slot_duration_min: number;
  capacity: number;
  created_at?: string | null;
}

export interface MarketplaceServiceScheduleException {
  id: string;
  service_location_id: string;
  date: string;
  is_closed: boolean;
  time_from?: string | null;
  time_to?: string | null;
  capacity_override?: number | null;
  created_at?: string | null;
}

export interface MarketplaceServiceSchedule {
  rules: MarketplaceServiceScheduleRule[];
  exceptions: MarketplaceServiceScheduleException[];
}

export interface MarketplaceServiceAvailabilitySlot {
  service_location_id: string;
  location_id: string;
  date: string;
  time_from: string;
  time_to: string;
  capacity: number;
}

export interface MarketplaceServiceAvailabilityResponse {
  items: MarketplaceServiceAvailabilitySlot[];
}

export type CatalogItemKind = "SERVICE" | "PRODUCT";
export type CatalogItemStatus = "DRAFT" | "ACTIVE" | "DISABLED" | "ARCHIVED";

export interface CatalogItemImage {
  url: string;
  caption?: string | null;
}

export interface CatalogItem {
  id: string;
  kind: CatalogItemKind;
  title: string;
  description?: string | null;
  category?: string | null;
  images?: CatalogItemImage[] | null;
  baseUom: string;
  status: CatalogItemStatus;
  createdAt: string;
  updatedAt: string;
  activeOffersCount?: number | null;
}

export interface CatalogItemInput {
  kind: CatalogItemKind;
  title: string;
  description?: string | null;
  category?: string | null;
  images?: CatalogItemImage[] | null;
  baseUom: string;
  status?: CatalogItemStatus;
}

export type OfferLocationScope = "all" | "selected";
export type OfferAvailability = "always" | "schedule" | "capacity";

export interface Offer {
  id: string;
  catalogItemId: string;
  locationScope: OfferLocationScope;
  locationIds?: string[] | null;
  price: number;
  currency: string;
  vatRate?: number | null;
  availability: OfferAvailability;
  active: boolean;
  validFrom?: string | null;
  validTo?: string | null;
  meta?: Record<string, string | number | boolean | null> | null;
}

export interface OfferInput {
  catalogItemId: string;
  locationScope: OfferLocationScope;
  locationIds?: string[] | null;
  price: number;
  currency: string;
  vatRate?: number | null;
  availability: OfferAvailability;
  active: boolean;
  validFrom?: string | null;
  validTo?: string | null;
  meta?: Record<string, string | number | boolean | null> | null;
}

export type OrderStatus =
  | "CREATED"
  | "PAID"
  | "AUTHORIZED"
  | "CONFIRMED"
  | "CONFIRMED_BY_PARTNER"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "CANCELLED"
  | "REFUNDED"
  | "DISPUTED";

export type PaymentStatus = "PAID" | "AUTH" | "AUTHORIZED" | "FAILED" | "REFUNDED" | "PENDING";

export interface OrderItem {
  offerId: string;
  title?: string | null;
  qty: number;
  unitPrice: number;
  amount: number;
}

export interface OrderDocumentLink {
  id: string;
  type: string;
  status: string;
  signatureStatus?: string | null;
  edoStatus?: string | null;
  url?: string | null;
  updatedAt?: string | null;
}

export interface MarketplaceOrder {
  id: string;
  clientId: string;
  clientName?: string | null;
  clientEmail?: string | null;
  clientPhone?: string | null;
  vehiclePlate?: string | null;
  partnerId: string;
  items: OrderItem[];
  itemsCount?: number | null;
  status: OrderStatus;
  paymentStatus?: PaymentStatus | null;
  paymentRef?: string | null;
  totalAmount?: number | null;
  vatAmount?: number | null;
  currency?: string | null;
  serviceTitle?: string | null;
  stationId?: string | null;
  stationName?: string | null;
  locationName?: string | null;
  documents?: OrderDocumentLink[] | null;
  documentsStatus?: string | null;
  correlationId?: string | null;
  slaResponseDueAt?: string | null;
  slaCompletionDueAt?: string | null;
  slaResponseRemainingSeconds?: number | null;
  slaCompletionRemainingSeconds?: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface SettlementFeeExplain {
  amount: number;
  basis: string;
  rate?: number | null;
  explain: string;
}

export interface SettlementPenaltySourceRef {
  audit_event_id?: string | null;
  sla_event_id?: string | null;
}

export interface SettlementPenalty {
  type: string;
  amount: number;
  reason?: string | null;
  source_ref?: SettlementPenaltySourceRef | null;
}

export interface OrderSettlementSnapshot {
  settlement_snapshot_id?: string | null;
  finalized_at?: string | null;
  hash?: string | null;
}

export interface MarketplaceOrderSettlementBreakdown {
  order_id: string;
  currency: string;
  gross_amount: number;
  platform_fee: SettlementFeeExplain;
  penalties: SettlementPenalty[];
  partner_net: number;
  snapshot?: OrderSettlementSnapshot | null;
}

export interface MarketplaceOrderActionResult {
  orderId: string;
  status: OrderStatus;
  correlationId?: string | null;
}

export interface MarketplaceOrderEvent {
  id: string;
  type: string;
  status?: string | null;
  note?: string | null;
  actor?: string | null;
  createdAt: string;
}

export interface MarketplaceOrderSlaMetric {
  metric: string;
  threshold?: number | null;
  measured?: number | null;
  status?: "OK" | "VIOLATION" | "UNKNOWN" | null;
  deadlineAt?: string | null;
  remainingSeconds?: number | null;
  totalSeconds?: number | null;
  reason?: string | null;
  penalty?: string | null;
}

export interface MarketplaceOrderSlaResponse {
  obligations?: MarketplaceOrderSlaMetric[] | null;
}

export interface MarketplaceOrderPayoutImpact {
  netAmount?: number | null;
  penalties?: number | null;
  currency?: string | null;
}

export type RefundStatus = "OPEN" | "UNDER_REVIEW" | "APPROVED" | "DENIED" | "COMPLETED";

export interface RefundEvidence {
  id: string;
  name?: string | null;
  url?: string | null;
}

export interface RefundEvent {
  id: string;
  status: string;
  note?: string | null;
  createdAt: string;
}

export interface RefundRequest {
  id: string;
  orderId: string;
  status: RefundStatus;
  amount: number;
  reason?: string | null;
  requestedAmount?: number | null;
  note?: string | null;
  evidence?: RefundEvidence[] | null;
  events?: RefundEvent[] | null;
  createdAt: string;
}

export interface RefundActionResult {
  refundId: string;
  status: RefundStatus;
  correlationId?: string | null;
}

export interface MarketplaceDocument {
  id: string;
  type: string;
  status: string;
  signatureStatus?: string | null;
  edoStatus?: string | null;
  url?: string | null;
}

export interface MarketplaceDocumentFile {
  id: string;
  name: string;
  url?: string | null;
}

export interface MarketplaceEdoEvent {
  id: string;
  status: string;
  timestamp: string;
  description?: string | null;
}

export interface MarketplaceDocumentDetails extends MarketplaceDocument {
  files?: MarketplaceDocumentFile[] | null;
  signatures?: Array<{
    signer: string;
    status: string;
    signedAt?: string | null;
  }> | null;
  edoEvents?: MarketplaceEdoEvent[] | null;
}

export interface MarketplaceSettlementLink {
  id: string;
  status: string;
  periodStart?: string | null;
  periodEnd?: string | null;
  payoutBatchId?: string | null;
}

export interface MarketplacePayout {
  id: string;
  source: "MARKETPLACE" | "FUEL" | "ALL";
  periodStart: string;
  periodEnd: string;
  grossAmount: number;
  netAmount: number;
  status: string;
}

export interface MarketplaceSettlement extends MarketplacePayout {
  breakdowns?: Array<{
    category?: string | null;
    service?: string | null;
    amount: number;
    count?: number | null;
  }>;
  documents?: MarketplaceDocument[] | null;
}

export interface CsvImportRowError {
  row: number;
  message: string;
}

export interface CatalogImportPreview {
  headers: string[];
  rows: Record<string, string>[];
  errors: CsvImportRowError[];
  summary?: {
    rowsParsed?: number;
    willCreate?: number;
    willUpdate?: number;
    errorsCount?: number;
  } | null;
  correlationId?: string | null;
}

export interface CatalogImportSummary {
  created?: number;
  updated?: number;
  failed?: number;
  createdCount?: number;
  updatedCount?: number;
  skippedCount?: number;
  errors?: CsvImportRowError[] | null;
  correlationId?: string | null;
}

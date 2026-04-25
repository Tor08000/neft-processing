export type MarketplaceProductType = "SERVICE" | "PRODUCT";
export type MarketplacePriceModel = "FIXED" | "PER_UNIT" | "TIERED";

export interface MarketplaceProductSummary {
  id: string;
  type: MarketplaceProductType;
  title: string;
  short_description?: string | null;
  category?: string | null;
  price_model?: MarketplacePriceModel | null;
  price_summary?: string | null;
  partner_name?: string | null;
  partner_id?: string | null;
  published_at?: string | null;
}

export interface MarketplaceProductListResponse {
  items: MarketplaceProductSummary[];
  total?: number | null;
  limit?: number | null;
  offset?: number | null;
}

export interface MarketplacePartnerSummary {
  id?: string | null;
  company_name?: string | null;
  profile_url?: string | null;
  verified?: boolean | null;
}

export interface MarketplaceSlaObligation {
  metric: string;
  threshold: number;
  comparison?: string | null;
  window?: string | null;
  penalty?: string | null;
}

export interface MarketplaceSlaSummary {
  obligations?: MarketplaceSlaObligation[] | null;
  penalties?: string | null;
}

export interface MarketplaceProductDetails {
  id: string;
  type: MarketplaceProductType;
  title: string;
  description?: string | null;
  category?: string | null;
  price_model?: MarketplacePriceModel | null;
  price_summary?: string | null;
  price_config?: Record<string, unknown> | null;
  partner?: MarketplacePartnerSummary | null;
  sla_summary?: MarketplaceSlaSummary | null;
}

export interface MarketplaceOffer {
  id: string;
  subject_type?: MarketplaceProductType | null;
  subject_id?: string | null;
  title?: string | null;
  price_model?: MarketplacePriceModel | null;
  price_amount?: number | null;
  price_min?: number | null;
  price_max?: number | null;
  currency?: string | null;
  geo_scope?: string | null;
  location_ids?: string[] | null;
  terms?: Record<string, unknown> | null;
  valid_from?: string | null;
  valid_to?: string | null;
  price?: number | null;
  location_name?: string | null;
  availability?: string | null;
  conditions?: string | null;
  documents?: string[] | null;
}

export interface MarketplaceProductOffersResponse {
  items: MarketplaceOffer[];
  total?: number | null;
}

export interface MarketplacePartner {
  id?: string | null;
  name?: string | null;
  url?: string | null;
}

export interface MarketplaceServiceDetails {
  id: string;
  title: string;
  description?: string | null;
  category?: string | null;
  partner?: MarketplacePartner | null;
  offers?: MarketplaceOffer[] | null;
  terms?: string | null;
  documents?: string[] | null;
}

export type MarketplaceOrderStatus =
  | "CREATED"
  | "PENDING_PAYMENT"
  | "PAID"
  | "CONFIRMED"
  | "CONFIRMED_BY_PARTNER"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "DECLINED_BY_PARTNER"
  | "CANCELED_BY_CLIENT"
  | "CANCELLED"
  | "PAYMENT_FAILED"
  | "FAILED"
  | "ACCEPTED"
  | "REJECTED"
  | "CLOSED"
  | "REFUNDED";

export interface MarketplaceOrderSummary {
  id: string;
  client_id?: string | null;
  partner_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  subtotal_amount?: number | null;
  discount_amount?: number | null;
  total_amount?: number | null;
  currency?: string | null;
  status?: MarketplaceOrderStatus | null;
  payment_status?: string | null;
  payment_method?: string | null;
  audit_event_id?: string | null;
  external_ref?: string | null;
}

export interface MarketplaceOrdersResponse {
  items: MarketplaceOrderSummary[];
  total?: number | null;
  limit?: number | null;
  offset?: number | null;
}

export interface MarketplaceOrderLine {
  id: string;
  order_id?: string | null;
  offer_id?: string | null;
  subject_type?: string | null;
  subject_id?: string | null;
  title_snapshot: string;
  qty?: number | null;
  unit_price?: number | null;
  line_amount?: number | null;
  meta?: Record<string, unknown> | null;
}

export interface MarketplaceOrderProof {
  id: string;
  order_id?: string | null;
  kind?: string | null;
  attachment_id?: string | null;
  note?: string | null;
  created_at?: string | null;
  meta?: Record<string, unknown> | null;
}

export interface MarketplaceOrderDetails extends MarketplaceOrderSummary {
  lines?: MarketplaceOrderLine[] | null;
  proofs?: MarketplaceOrderProof[] | null;
  events?: MarketplaceOrderEvent[] | null;
}

export interface MarketplaceOrderEvent {
  id: string;
  order_id?: string | null;
  event_type: string;
  occurred_at?: string | null;
  payload_redacted?: Record<string, unknown> | null;
  actor_type?: "client" | "partner" | "admin" | "system" | string | null;
  actor_id?: string | null;
  audit_event_id?: string | null;
  created_at: string;
  before_status?: string | null;
  after_status?: string | null;
  reason_code?: string | null;
  comment?: string | null;
  meta?: Record<string, unknown> | null;
}


export interface MarketplaceOrderSlaMetric {
  id: string;
  order_id: string;
  contract_id: string;
  obligation_id: string;
  period_start: string;
  period_end: string;
  measured_value: number;
  status: string;
  breach_reason?: string | null;
  breach_severity?: string | null;
  created_at: string;
}

export interface MarketplaceOrderSlaResponse {
  items?: MarketplaceOrderSlaMetric[] | null;
}

export interface MarketplaceOrderConsequence {
  id: string;
  order_id: string;
  evaluation_id: string;
  consequence_type: string;
  amount: number;
  currency: string;
  billing_invoice_id?: string | null;
  billing_refund_id?: string | null;
  ledger_tx_id?: string | null;
  status: string;
  created_at: string;
}

export interface MarketplaceOrderConsequencesResponse {
  items?: MarketplaceOrderConsequence[] | null;
}


export interface MarketplaceCreateOrderPayload {
  items: { offer_id: string; qty?: number | null }[];
  payment_method: string;
}

export interface MarketplaceCreateOrderResponse {
  id?: string | null;
  status?: string | null;
  message?: string | null;
}

export type MarketplaceClientEventType =
  | "marketplace.offer_viewed"
  | "marketplace.offer_clicked"
  | "marketplace.search_performed"
  | "marketplace.order_created"
  | "marketplace.order_paid"
  | "marketplace.order_canceled"
  | "marketplace.product_viewed"
  | "marketplace.service_viewed"
  | "marketplace.filters_changed"
  | "marketplace.checkout_started";

export type MarketplaceClientEntityType = "OFFER" | "PRODUCT" | "SERVICE" | "ORDER" | "NONE";

export type MarketplaceClientEventSource = "client_portal" | "web" | "mobile" | "api";

export interface MarketplaceClientEventInput {
  event_type: MarketplaceClientEventType;
  entity_type: MarketplaceClientEntityType;
  entity_id?: string | null;
  session_id?: string | null;
  source: MarketplaceClientEventSource;
  page?: string | null;
  utm?: Record<string, unknown> | null;
  payload?: Record<string, unknown> | null;
  client_ts?: string | null;
  request_id?: string | null;
  idempotency_key?: string | null;
}

export interface MarketplaceClientEventsIngestResponse {
  accepted: number;
  rejected: number;
}

export interface MarketplaceRecommendationPrice {
  currency: string;
  model: string;
  amount?: number | null;
}

export interface MarketplaceRecommendationPreview {
  image_url?: string | null;
  short?: string | null;
}

export interface MarketplaceRecommendationItem {
  offer_id: string;
  title: string;
  subject_type: MarketplaceProductType;
  price?: MarketplaceRecommendationPrice | null;
  partner_id: string;
  category?: string | null;
  preview?: MarketplaceRecommendationPreview | null;
  reason_hint?: string | null;
}

export interface MarketplaceRecommendationsResponse {
  items: MarketplaceRecommendationItem[];
  generated_at: string;
  ttl_seconds: number;
}

export interface MarketplaceRecommendationWhyReason {
  code: string;
  label: string;
  evidence?: Record<string, unknown> | null;
}

export interface MarketplaceRecommendationScoreBreakdown {
  signal: string;
  value: number;
}

export interface MarketplaceRecommendationWhyResponse {
  offer_id: string;
  reasons: MarketplaceRecommendationWhyReason[];
  score_breakdown: MarketplaceRecommendationScoreBreakdown[];
}

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
  price?: number | null;
  currency?: string | null;
  location_name?: string | null;
  availability?: string | null;
  conditions?: string | null;
  documents?: string[] | null;
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

export interface MarketplaceOrderSummary {
  id: string;
  service_title?: string | null;
  partner_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  subtotal_amount?: number | null;
  discount_amount?: number | null;
  total_amount?: number | null;
  currency?: string | null;
  status?: string | null;
  payment_status?: string | null;
  payment_method?: string | null;
  documents_status?: string | null;
  sla_status?: "OK" | "VIOLATION" | "UNKNOWN" | null;
  price_snapshot?: {
    total_amount?: number | null;
    currency?: string | null;
  } | null;
}

export interface MarketplaceOrdersResponse {
  items: MarketplaceOrderSummary[];
  total?: number | null;
  limit?: number | null;
  offset?: number | null;
}

export interface MarketplaceOrderDetails {
  id: string;
  status?: string | null;
  service_title?: string | null;
  partner_name?: string | null;
  subtotal_amount?: number | null;
  discount_amount?: number | null;
  total_amount?: number | null;
  currency?: string | null;
  payment_status?: string | null;
  payment_method?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  documents_status?: string | null;
  price_snapshot?: {
    total_amount?: number | null;
    currency?: string | null;
  } | null;
}

export interface MarketplaceOrderEvent {
  id: string;
  event_type: string;
  status?: string | null;
  note?: string | null;
  actor_type?: "client" | "partner" | "system" | string | null;
  created_at: string;
}

export interface MarketplaceOrderDocumentFile {
  id: string;
  name?: string | null;
  url?: string | null;
}

export interface MarketplaceOrderDocument {
  id: string;
  type: string;
  status?: string | null;
  signature_status?: string | null;
  edo_status?: string | null;
  url?: string | null;
  files?: MarketplaceOrderDocumentFile[] | null;
}

export interface MarketplaceOrderDocumentsResponse {
  items: MarketplaceOrderDocument[];
}

export interface MarketplaceOrderSlaMetric {
  metric: string;
  threshold?: number | null;
  comparison?: string | null;
  window?: string | null;
  measured_value?: number | null;
  status?: "OK" | "VIOLATION" | "UNKNOWN" | null;
  deadline_at?: string | null;
  reason?: string | null;
  penalty?: string | null;
}

export interface MarketplaceOrderSlaResponse {
  obligations?: MarketplaceOrderSlaMetric[] | null;
}

export interface MarketplaceOrderConsequence {
  id: string;
  type?: string | null;
  amount?: number | null;
  currency?: string | null;
  reason?: string | null;
  created_at?: string | null;
}

export interface MarketplaceOrderConsequencesResponse {
  items?: MarketplaceOrderConsequence[] | null;
}

export interface MarketplaceOrderInvoice {
  id: string;
  invoice_number?: string | null;
  status?: string | null;
  amount?: number | null;
  currency?: string | null;
  url?: string | null;
}

export interface MarketplaceCreateOrderPayload {
  items: { offer_id: string; qty?: number | null }[];
  payment_method: string;
}

export interface MarketplaceProductOrderPayload {
  product_id: string;
  qty?: number | null;
  notes?: string | null;
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

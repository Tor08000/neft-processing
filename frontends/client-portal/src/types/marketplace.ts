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
  total_amount?: number | null;
  currency?: string | null;
  status?: string | null;
  documents_status?: string | null;
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
  total_amount?: number | null;
  currency?: string | null;
  created_at?: string | null;
  documents_status?: string | null;
}

export interface MarketplaceOrderEvent {
  id: string;
  type: string;
  status?: string | null;
  note?: string | null;
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

export interface MarketplaceCreateOrderPayload {
  service_id: string;
  offer_id: string;
  qty?: number | null;
  comment?: string | null;
}

export interface MarketplaceProductOrderPayload {
  product_id: string;
  qty?: number | null;
  notes?: string | null;
}

export interface MarketplaceCreateOrderResponse {
  order_id?: string | null;
  status?: string | null;
  message?: string | null;
}

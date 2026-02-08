export type MarketplaceModerationStatus = "DRAFT" | "PENDING_REVIEW" | "ACTIVE" | "SUSPENDED" | "ARCHIVED";

export type MarketplaceModerationEntityType = "PRODUCT" | "SERVICE" | "OFFER";

export type MarketplaceModerationReasonCode =
  | "INVALID_CONTENT"
  | "MISSING_INFO"
  | "POLICY_VIOLATION"
  | "DUPLICATE"
  | "WRONG_CATEGORY"
  | "PRICING_ISSUE"
  | "GEO_SCOPE_ISSUE"
  | "ENTITLEMENTS_ISSUE"
  | "OTHER";

export interface MarketplaceModerationQueueItem {
  type: MarketplaceModerationEntityType;
  id: string;
  partner_id: string;
  title: string;
  status: MarketplaceModerationStatus;
  submitted_at?: string | null;
  updated_at?: string | null;
}

export interface MarketplaceModerationQueueResponse {
  items: MarketplaceModerationQueueItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface MarketplaceModerationAuditItem {
  id: string;
  actor_user_id?: string | null;
  actor_role?: string | null;
  action: "APPROVE" | "REJECT" | "SUSPEND";
  reason_code?: MarketplaceModerationReasonCode | null;
  comment?: string | null;
  before_status?: MarketplaceModerationStatus | null;
  after_status?: MarketplaceModerationStatus | null;
  created_at: string;
  meta?: Record<string, unknown> | null;
}

export interface MarketplaceModerationAuditResponse {
  items: MarketplaceModerationAuditItem[];
}

export interface MarketplaceProductCardDetail {
  id: string;
  partner_id: string;
  title: string;
  description: string;
  category: string;
  status: MarketplaceModerationStatus;
  tags: string[];
  attributes: Record<string, unknown>;
  variants: Record<string, unknown>[];
  media: Array<{
    attachment_id: string;
    bucket: string;
    path: string;
    checksum?: string | null;
    size?: number | null;
    mime?: string | null;
    sort_index?: number | null;
    created_at?: string | null;
  }>;
  created_at: string;
  updated_at?: string | null;
}

export interface MarketplaceServiceDetail {
  id: string;
  partner_id: string;
  title: string;
  description?: string | null;
  category: string;
  status: MarketplaceModerationStatus;
  tags: string[];
  attributes: Record<string, unknown>;
  duration_min: number;
  requirements?: string | null;
  media: Array<{
    attachment_id: string;
    bucket: string;
    path: string;
    checksum?: string | null;
    size?: number | null;
    mime?: string | null;
    sort_index?: number | null;
    created_at?: string | null;
  }>;
  created_at: string;
  updated_at?: string | null;
  locations: Array<{
    id: string;
    service_id: string;
    location_id: string;
    address?: string | null;
    latitude?: number | null;
    longitude?: number | null;
    is_active: boolean;
    created_at?: string | null;
  }>;
  schedule?: {
    rules: Array<{
      id: string;
      service_location_id: string;
      weekday: number;
      time_from: string;
      time_to: string;
      slot_duration_min: number;
      capacity: number;
      created_at?: string | null;
    }>;
    exceptions: Array<{
      id: string;
      service_location_id: string;
      date: string;
      is_closed: boolean;
      time_from?: string | null;
      time_to?: string | null;
      capacity_override?: number | null;
      created_at?: string | null;
    }>;
  } | null;
}

export interface MarketplaceOfferDetail {
  id: string;
  partner_id: string;
  subject_type: string;
  subject_id: string;
  title_override?: string | null;
  description_override?: string | null;
  status: MarketplaceModerationStatus;
  moderation_comment?: string | null;
  currency: string;
  price_model: string;
  price_amount?: number | null;
  price_min?: number | null;
  price_max?: number | null;
  vat_rate?: number | null;
  terms: Record<string, unknown>;
  geo_scope: string;
  location_ids: string[];
  region_code?: string | null;
  entitlement_scope: string;
  allowed_subscription_codes: string[];
  allowed_client_ids: string[];
  valid_from?: string | null;
  valid_to?: string | null;
  created_at: string;
  updated_at?: string | null;
}

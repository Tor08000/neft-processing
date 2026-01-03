export type MarketplaceModerationStatus = "DRAFT" | "PENDING_REVIEW" | "APPROVED" | "REJECTED";

export interface MarketplaceModerationProduct {
  id: string;
  partner_id: string;
  title: string;
  category: string;
  status: string;
  moderation_status: MarketplaceModerationStatus;
  moderation_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface MarketplaceModerationQueueResponse {
  items: MarketplaceModerationProduct[];
  total: number;
  limit: number;
  offset: number;
}

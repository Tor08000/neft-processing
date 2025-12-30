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
  | "CONFIRMED_BY_PARTNER"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "CANCELLED"
  | "REFUNDED"
  | "DISPUTED";

export interface OrderItem {
  offerId: string;
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
}

export interface MarketplaceOrder {
  id: string;
  clientId: string;
  partnerId: string;
  items: OrderItem[];
  status: OrderStatus;
  paymentRef?: string | null;
  documents?: OrderDocumentLink[] | null;
  createdAt: string;
  updatedAt: string;
}

export interface MarketplaceOrderActionResult {
  orderId: string;
  status: OrderStatus;
  correlationId?: string | null;
}

export type RefundStatus = "OPEN" | "UNDER_REVIEW" | "APPROVED" | "DENIED" | "COMPLETED";

export interface RefundRequest {
  id: string;
  orderId: string;
  status: RefundStatus;
  amount: number;
  reason?: string | null;
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
}

export interface CatalogImportSummary {
  created: number;
  updated: number;
  failed: number;
  errors?: CsvImportRowError[] | null;
}

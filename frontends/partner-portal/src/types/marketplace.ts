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
  createdAt: string;
  updatedAt: string;
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

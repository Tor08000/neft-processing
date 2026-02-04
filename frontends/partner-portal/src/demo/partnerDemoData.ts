import type {
  CatalogItem,
  MarketplaceOrder,
  MarketplaceProductSummary,
} from "../types/marketplace";
import type {
  PriceAnalyticsInsight,
  PriceAnalyticsOffer,
  PriceAnalyticsSeriesPoint,
  PriceAnalyticsVersion,
} from "../types/prices";
import type {
  PartnerBalance,
  PartnerDocument,
  PartnerExportJob,
  PartnerLedgerEntry,
  PartnerPayoutRequest,
} from "../types/partnerFinance";

const toDate = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() - offsetDays);
  return value.toISOString().slice(0, 10);
};

const toDateTime = (offsetDays: number) => {
  const value = new Date();
  value.setDate(value.getDate() - offsetDays);
  value.setHours(10 + (offsetDays % 6) * 2, 12, 0, 0);
  return value.toISOString();
};

export const demoOrders: MarketplaceOrder[] = [
  {
    id: "MP-1001",
    clientId: "client-01",
    clientName: "ООО «Альфа»",
    partnerId: "demo-partner",
    items: [{ offerId: "svc-101", title: "Комплексная мойка", qty: 1, unitPrice: 1800, amount: 1800 }],
    itemsCount: 1,
    status: "CREATED",
    totalAmount: 1800,
    currency: "RUB",
    serviceTitle: "Комплексная мойка",
    documentsStatus: "pending",
    slaResponseDueAt: toDateTime(0),
    slaResponseRemainingSeconds: 7200,
    createdAt: toDateTime(0),
    updatedAt: toDateTime(0),
  },
  {
    id: "MP-1002",
    clientId: "client-02",
    clientName: "ИП Громов",
    partnerId: "demo-partner",
    items: [{ offerId: "svc-202", title: "Диагностика", qty: 1, unitPrice: 2500, amount: 2500 }],
    itemsCount: 1,
    status: "IN_PROGRESS",
    totalAmount: 2500,
    currency: "RUB",
    serviceTitle: "Диагностика",
    documentsStatus: "ok",
    slaCompletionDueAt: toDateTime(1),
    slaCompletionRemainingSeconds: 14400,
    createdAt: toDateTime(1),
    updatedAt: toDateTime(0),
  },
  {
    id: "MP-1003",
    clientId: "client-03",
    clientName: "ООО «Бета»",
    partnerId: "demo-partner",
    items: [{ offerId: "svc-303", title: "Шиномонтаж", qty: 1, unitPrice: 3200, amount: 3200 }],
    itemsCount: 1,
    status: "COMPLETED",
    totalAmount: 3200,
    currency: "RUB",
    serviceTitle: "Шиномонтаж",
    documentsStatus: "signed",
    createdAt: toDateTime(2),
    updatedAt: toDateTime(1),
  },
  {
    id: "MP-1004",
    clientId: "client-04",
    clientName: "ООО «Север»",
    partnerId: "demo-partner",
    items: [{ offerId: "svc-404", title: "Техосмотр", qty: 1, unitPrice: 4200, amount: 4200 }],
    itemsCount: 1,
    status: "PAID",
    totalAmount: 4200,
    currency: "RUB",
    serviceTitle: "Техосмотр",
    documentsStatus: "pending",
    createdAt: toDateTime(3),
    updatedAt: toDateTime(3),
  },
  {
    id: "MP-1005",
    clientId: "client-05",
    clientName: "ООО «Восток»",
    partnerId: "demo-partner",
    items: [{ offerId: "svc-505", title: "Замена масла", qty: 1, unitPrice: 2600, amount: 2600 }],
    itemsCount: 1,
    status: "COMPLETED",
    totalAmount: 2600,
    currency: "RUB",
    serviceTitle: "Замена масла",
    documentsStatus: "signed",
    createdAt: toDateTime(4),
    updatedAt: toDateTime(2),
  },
];

export const demoOrdersKpis = {
  ordersToday: 2,
  pendingConfirmation: 3,
  docsPending: 2,
  total: demoOrders.length,
};

export const demoCatalogItems: CatalogItem[] = [
  {
    id: "svc-101",
    kind: "SERVICE",
    title: "Комплексная мойка",
    description: "Полная мойка кузова и салона.",
    category: "Автомойка",
    baseUom: "услуга",
    status: "ACTIVE",
    createdAt: toDateTime(20),
    updatedAt: toDateTime(2),
    activeOffersCount: 4,
  },
  {
    id: "svc-202",
    kind: "SERVICE",
    title: "Диагностика",
    description: "Комплексная диагностика автомобиля.",
    category: "Диагностика",
    baseUom: "услуга",
    status: "ACTIVE",
    createdAt: toDateTime(30),
    updatedAt: toDateTime(6),
    activeOffersCount: 2,
  },
  {
    id: "svc-303",
    kind: "SERVICE",
    title: "Шиномонтаж",
    description: "Сезонная замена шин.",
    category: "Сервис",
    baseUom: "услуга",
    status: "DISABLED",
    createdAt: toDateTime(40),
    updatedAt: toDateTime(8),
    activeOffersCount: 0,
  },
];

export const demoMarketplaceProducts: MarketplaceProductSummary[] = [
  {
    id: "prod-101",
    partner_id: "demo-partner",
    type: "SERVICE",
    title: "Комплексная мойка",
    category: "Автомойка",
    price_model: "FIXED",
    price_config: { amount: 1800, currency: "RUB" },
    status: "PUBLISHED",
    published_at: toDateTime(15),
    updated_at: toDateTime(3),
  },
  {
    id: "prod-202",
    partner_id: "demo-partner",
    type: "SERVICE",
    title: "Шиномонтаж",
    category: "Сервис",
    price_model: "FIXED",
    price_config: { amount: 3200, currency: "RUB" },
    status: "DRAFT",
    updated_at: toDateTime(5),
  },
  {
    id: "prod-303",
    partner_id: "demo-partner",
    type: "PRODUCT",
    title: "Комплект фильтров",
    category: "Запчасти",
    price_model: "PER_UNIT",
    price_config: { unit: "item", amount_per_unit: 950, currency: "RUB" },
    status: "ARCHIVED",
    updated_at: toDateTime(18),
  },
];

export const demoAnalyticsVersions: PriceAnalyticsVersion[] = [
  {
    price_version_id: "PR-2024.08",
    published_at: toDateTime(18),
    orders_count: 124,
    revenue_total: 456000,
    avg_order_value: 3677,
    refunds_count: 2,
  },
  {
    price_version_id: "PR-2024.07",
    published_at: toDateTime(45),
    orders_count: 98,
    revenue_total: 332000,
    avg_order_value: 3388,
    refunds_count: 1,
  },
];

export const demoAnalyticsOffers: PriceAnalyticsOffer[] = [
  { offer_id: "Комплексная мойка", orders_count: 42, conversion_rate: 0.34, avg_price: 1800, revenue_total: 75600 },
  { offer_id: "Диагностика", orders_count: 28, conversion_rate: 0.22, avg_price: 2500, revenue_total: 70000 },
  { offer_id: "Шиномонтаж", orders_count: 18, conversion_rate: 0.18, avg_price: 3200, revenue_total: 57600 },
];

export const demoAnalyticsInsights: PriceAnalyticsInsight[] = [
  {
    type: "trend",
    severity: "INFO",
    message: "Заказы растут +12% после обновления прайса.",
    price_version_id: "PR-2024.08",
  },
  {
    type: "sla",
    severity: "WARN",
    message: "Есть риск по SLA у 5% заказов — проверьте загруженность.",
  },
];

export const demoAnalyticsSeries: PriceAnalyticsSeriesPoint[] = Array.from({ length: 7 }, (_, index) => ({
  date: toDate(6 - index),
  orders_count: 12 + index * 3,
  revenue_total: 42000 + index * 6500,
}));

export const demoBalance: PartnerBalance = {
  partner_org_id: "demo-partner",
  currency: "RUB",
  balance_available: 120000,
  balance_pending: 35000,
  balance_blocked: 5000,
};

export const demoLedgerTotals = { in: 240000, out: 120000, net: 120000 };

export const demoLedger: PartnerLedgerEntry[] = [
  {
    id: "led-101",
    partner_org_id: "demo-partner",
    order_id: "MP-1001",
    entry_type: "ORDER_COMPLETED",
    amount: 1800,
    currency: "RUB",
    direction: "IN",
    meta_json: { source_type: "order", source_id: "MP-1001" },
    created_at: toDateTime(1),
  },
  {
    id: "led-202",
    partner_org_id: "demo-partner",
    order_id: "MP-1003",
    entry_type: "PAYOUT",
    amount: 3200,
    currency: "RUB",
    direction: "OUT",
    meta_json: { source_type: "payout_request", source_id: "PO-889" },
    created_at: toDateTime(4),
  },
];

export const demoExportJobs: PartnerExportJob[] = [
  {
    id: "exp-101",
    org_id: "demo-partner",
    created_by_user_id: "demo-user",
    report_type: "settlement_chain",
    format: "CSV",
    status: "DONE",
    filters: { from: toDate(30), to: toDate(0) },
    file_name: "settlements_demo.csv",
    processed_rows: 12,
    created_at: toDateTime(6),
  },
];

export const demoPayouts: PartnerPayoutRequest[] = [
  {
    id: "pay-101",
    partner_org_id: "demo-partner",
    amount: 45000,
    currency: "RUB",
    status: "APPROVED",
    blocked_reason: null,
    created_at: toDateTime(8),
  },
  {
    id: "pay-102",
    partner_org_id: "demo-partner",
    amount: 18000,
    currency: "RUB",
    status: "PENDING",
    blocked_reason: null,
    created_at: toDateTime(3),
  },
];

export const demoInvoices: PartnerDocument[] = [
  {
    id: "inv-2024-07",
    partner_org_id: "demo-partner",
    period_from: toDate(30),
    period_to: toDate(1),
    total_amount: 98000,
    currency: "RUB",
    status: "ISSUED",
    created_at: toDateTime(1),
  },
];

export const demoActs: PartnerDocument[] = [
  {
    id: "act-2024-06",
    partner_org_id: "demo-partner",
    period_from: toDate(60),
    period_to: toDate(31),
    total_amount: 87500,
    currency: "RUB",
    status: "SIGNED",
    created_at: toDateTime(20),
  },
];

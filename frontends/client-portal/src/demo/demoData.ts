export type OverviewVehicle = {
  id: string;
  plate: string;
  model: string;
  status: "active" | "service";
  mileage?: number;
  fuelUsage?: number;
};

export type OverviewOperation = {
  id: string;
  date: string;
  type: string;
  amount: number;
  status: "paid" | "pending" | "failed";
};

export type OverviewData = {
  balance: number;
  limit: number;
  fuelSpent: number;
  fleetStats?: {
    vehicles: number;
    activeCards: number;
    fuelLimit: number;
    overdue: number;
  };
  vehicles: OverviewVehicle[];
  operations: OverviewOperation[];
};

export const demoOverviewData: Record<"personal" | "fleet", OverviewData> = {
  personal: {
    balance: 2_450_000,
    limit: 3_000_000,
    fuelSpent: 820,
    vehicles: [
      {
        id: "car-1",
        plate: "А123ВС 77",
        model: "BMW X5 · 2023",
        status: "active",
        mileage: 18_450,
        fuelUsage: 8.7,
      },
    ],
    operations: [
      {
        id: "op-1",
        date: "12 сен, 09:10",
        type: "Заправка · Лукойл",
        amount: -4_250,
        status: "paid",
      },
      {
        id: "op-2",
        date: "10 сен, 17:40",
        type: "Оплата · Счёт №8421",
        amount: 150_000,
        status: "paid",
      },
      {
        id: "op-3",
        date: "07 сен, 12:05",
        type: "Списание · Телематика",
        amount: -8_400,
        status: "pending",
      },
    ],
  },
  fleet: {
    balance: 12_450_000,
    limit: 18_000_000,
    fuelSpent: 4_120,
    fleetStats: {
      vehicles: 54,
      activeCards: 48,
      fuelLimit: 6_200_000,
      overdue: 125_000,
    },
    vehicles: [
      {
        id: "fleet-1",
        plate: "М245НЕ 199",
        model: "Mercedes Sprinter",
        status: "active",
        mileage: 98_200,
        fuelUsage: 12.4,
      },
      {
        id: "fleet-2",
        plate: "С381АК 178",
        model: "Toyota Camry",
        status: "service",
        mileage: 74_210,
      },
      {
        id: "fleet-3",
        plate: "Т902ОР 77",
        model: "Volkswagen Crafter",
        status: "active",
        mileage: 65_120,
        fuelUsage: 11.8,
      },
    ],
    operations: [
      {
        id: "f-op-1",
        date: "Сегодня, 08:15",
        type: "Заправка · Роснефть",
        amount: -18_250,
        status: "paid",
      },
      {
        id: "f-op-2",
        date: "Вчера, 19:30",
        type: "Счёт · Автопарк",
        amount: -56_000,
        status: "pending",
      },
      {
        id: "f-op-3",
        date: "08 сен, 11:20",
        type: "Оплата · Счёт №8412",
        amount: 260_000,
        status: "paid",
      },
    ],
  },
};

export type DemoDocument = {
  id: string;
  type: string;
  status: string;
  date: string;
  download_url: string;
};

export const demoDocuments: DemoDocument[] = [
  {
    id: "doc-001",
    type: "Счёт №214",
    status: "Подписан",
    date: "2024-09-01",
    download_url: "#",
  },
  {
    id: "doc-002",
    type: "Акт №98",
    status: "Ожидает подписи",
    date: "2024-09-05",
    download_url: "#",
  },
  {
    id: "doc-003",
    type: "Договор на топливо",
    status: "Подписан",
    date: "2024-08-21",
    download_url: "#",
  },
  {
    id: "doc-004",
    type: "Счёт №205",
    status: "Отправлен",
    date: "2024-08-12",
    download_url: "#",
  },
];

export type DemoOperation = {
  id: string;
  created_at: string;
  status: string;
  amount: number;
  currency: string;
  card_id: string;
  merchant_id?: string | null;
  product_type?: string | null;
  quantity?: number | string | null;
};

export const demoOperations: DemoOperation[] = [
  {
    id: "op-001",
    created_at: "2024-09-12T08:10:00Z",
    status: "APPROVED",
    amount: -4250,
    currency: "RUB",
    card_id: "**** 2345",
    merchant_id: "Лукойл",
    product_type: "ДТ",
    quantity: 48,
  },
  {
    id: "op-002",
    created_at: "2024-09-11T14:32:00Z",
    status: "SETTLED",
    amount: -15200,
    currency: "RUB",
    card_id: "**** 7812",
    merchant_id: "Газпромнефть",
    product_type: "АИ-95",
    quantity: 120,
  },
  {
    id: "op-003",
    created_at: "2024-09-09T09:55:00Z",
    status: "DECLINED",
    amount: -890,
    currency: "RUB",
    card_id: "**** 4100",
    merchant_id: "Татнефть",
    product_type: "АИ-92",
    quantity: 8,
  },
  {
    id: "op-004",
    created_at: "2024-09-07T18:20:00Z",
    status: "APPROVED",
    amount: -9900,
    currency: "RUB",
    card_id: "**** 2211",
    merchant_id: "Роснефть",
    product_type: "ДТ",
    quantity: 74,
  },
];

export type DemoVehicle = {
  id: string;
  plate: string;
  model: string;
  status: "active" | "service";
};

export const demoVehicles: DemoVehicle[] = [
  { id: "veh-01", plate: "А123ВС 77", model: "BMW X5 · 2023", status: "active" },
  { id: "veh-02", plate: "М245НЕ 199", model: "Mercedes Sprinter", status: "active" },
  { id: "veh-03", plate: "Т902ОР 77", model: "Volkswagen Crafter", status: "service" },
];

export type DemoFleetUser = {
  id: string;
  email: string;
  status: string;
  role: string;
};

export const demoFleetUsers: DemoFleetUser[] = [
  { id: "fleet-user-1", email: "maria@demo.test", status: "ACTIVE", role: "manager" },
  { id: "fleet-user-2", email: "ivan@demo.test", status: "ACTIVE", role: "viewer" },
  { id: "fleet-user-3", email: "alex@demo.test", status: "INVITED", role: "admin" },
];

export type DemoLimit = {
  id: string;
  scope: string;
  period: string;
  amount: number;
  status: string;
};

export const demoLimits: DemoLimit[] = [
  { id: "limit-01", scope: "Группа · Север", period: "Месяц", amount: 120000, status: "Активен" },
  { id: "limit-02", scope: "Карта · 7812", period: "Неделя", amount: 25000, status: "Активен" },
  { id: "limit-03", scope: "Водитель · Иван И.", period: "День", amount: 3500, status: "Ожидает" },
];

export type DemoReport = {
  id: string;
  title: string;
  period: string;
  status: string;
};

export const demoReports: DemoReport[] = [
  { id: "report-01", title: "Отчёт по расходам", period: "Август 2024", status: "Готов" },
  { id: "report-02", title: "Контроль лимитов", period: "Сентябрь 2024", status: "В процессе" },
];

export type DemoDocumentsSummary = {
  issued: number;
  signed: number;
  edo_pending: number;
  edo_failed: number;
  attention: Array<{ id: string; title: string; status: string }>;
};

export const demoDocumentsSummary: DemoDocumentsSummary = {
  issued: 24,
  signed: 19,
  edo_pending: 4,
  edo_failed: 1,
  attention: [
    { id: "doc-att-1", title: "Счёт №214", status: "Ожидает подписи" },
    { id: "doc-att-2", title: "Акт №98", status: "Требует ЭДО" },
  ],
};

export const demoAnalyticsDailyMetrics = {
  from: "2024-09-01",
  to: "2024-09-30",
  currency: "RUB",
  spend: {
    total: 2_540_000,
    series: [
      { date: "2024-09-24", value: 120_000 },
      { date: "2024-09-25", value: 132_000 },
      { date: "2024-09-26", value: 98_000 },
      { date: "2024-09-27", value: 160_000 },
      { date: "2024-09-28", value: 142_000 },
      { date: "2024-09-29", value: 118_000 },
      { date: "2024-09-30", value: 150_000 },
    ],
  },
  orders: {
    total: 418,
    completed: 392,
    refunds: 6,
    series: [
      { date: "2024-09-24", value: 58 },
      { date: "2024-09-25", value: 64 },
      { date: "2024-09-26", value: 52 },
      { date: "2024-09-27", value: 68 },
      { date: "2024-09-28", value: 60 },
      { date: "2024-09-29", value: 54 },
      { date: "2024-09-30", value: 62 },
    ],
  },
  declines: {
    total: 14,
    top_reason: "Лимит превышен",
    series: [
      { date: "2024-09-24", value: 2 },
      { date: "2024-09-25", value: 1 },
      { date: "2024-09-26", value: 3 },
      { date: "2024-09-27", value: 2 },
      { date: "2024-09-28", value: 1 },
      { date: "2024-09-29", value: 3 },
      { date: "2024-09-30", value: 2 },
    ],
  },
  documents: {
    attention: 3,
  },
  exports: {
    attention: 1,
  },
  attention: [
    {
      id: "attention-1",
      title: "Истекает срок действия карты",
      description: "Проверьте карты водителей и обновите при необходимости.",
      href: "/client/cards",
      severity: "warning",
    },
  ],
};

export const demoAnalyticsDeclines = {
  total: 14,
  top_reasons: [
    { reason: "Лимит превышен", count: 6 },
    { reason: "Недостаточно средств", count: 4 },
    { reason: "Карта заблокирована", count: 4 },
  ],
  trend: [
    { date: "2024-09-24", reason: "Лимит превышен", count: 2 },
    { date: "2024-09-25", reason: "Недостаточно средств", count: 1 },
    { date: "2024-09-26", reason: "Карта заблокирована", count: 3 },
    { date: "2024-09-27", reason: "Лимит превышен", count: 2 },
    { date: "2024-09-28", reason: "Недостаточно средств", count: 1 },
    { date: "2024-09-29", reason: "Лимит превышен", count: 3 },
    { date: "2024-09-30", reason: "Карта заблокирована", count: 2 },
  ],
  expensive: [
    { id: "decline-1", reason: "Лимит превышен", amount: 28_500, station: "Лукойл · МКАД" },
    { id: "decline-2", reason: "Недостаточно средств", amount: 21_300, station: "Газпромнефть · Лесная" },
  ],
};

export const demoAnalyticsExportsSummary = {
  total: 6,
  ok: 5,
  mismatch: 1,
  items: [
    {
      id: "exp-001",
      status: "OK",
      mapping_version: "v2.3",
      checksum: "a1b2c3d4",
      created_at: "2024-09-30T09:42:00Z",
    },
    {
      id: "exp-002",
      status: "Mismatch",
      mapping_version: "v2.3",
      checksum: "b4c5d6e7",
      created_at: "2024-09-28T15:18:00Z",
    },
  ],
};

export type DemoClientAnalyticsSummary = {
  period: { from: string; to: string };
  summary: {
    transactions_count: number;
    total_spend: number;
    total_liters: number | null;
    active_cards: number;
    blocked_cards: number;
    unique_drivers: number;
    open_tickets: number;
    sla_breaches_first: number;
    sla_breaches_resolution: number;
  };
  timeseries: Array<{ date: string; spend: number; liters: number | null; count: number }>;
  tops: {
    cards: Array<{ card_id: string; label: string; spend: number; count: number; liters: number | null }>;
    drivers: Array<{ user_id: string; label: string; spend: number; count: number }>;
    stations: Array<{ station_id: string; label: string; spend: number; count: number; liters: number | null }>;
  };
  support: { open: number; avg_first_response_minutes: number | null; avg_resolve_minutes: number | null };
};

export const demoClientAnalyticsSummary: DemoClientAnalyticsSummary = {
  period: { from: "2024-08-12", to: "2024-09-11" },
  summary: {
    transactions_count: 412,
    total_spend: 2_540_000,
    total_liters: 31_200,
    active_cards: 46,
    blocked_cards: 3,
    unique_drivers: 38,
    open_tickets: 4,
    sla_breaches_first: 1,
    sla_breaches_resolution: 0,
  },
  timeseries: [
    { date: "2024-09-05", spend: 120_000, liters: 1500, count: 32 },
    { date: "2024-09-06", spend: 98_000, liters: 1120, count: 27 },
    { date: "2024-09-07", spend: 140_000, liters: 1760, count: 41 },
    { date: "2024-09-08", spend: 88_000, liters: 980, count: 22 },
    { date: "2024-09-09", spend: 156_000, liters: 2010, count: 45 },
    { date: "2024-09-10", spend: 130_000, liters: 1660, count: 36 },
    { date: "2024-09-11", spend: 122_000, liters: 1510, count: 33 },
  ],
  tops: {
    cards: [
      { card_id: "card-01", label: "Card · 2345", spend: 420_000, count: 65, liters: 5400 },
      { card_id: "card-02", label: "Card · 7812", spend: 310_000, count: 52, liters: 4020 },
    ],
    drivers: [
      { user_id: "driver-01", label: "Иван И.", spend: 380_000, count: 58 },
      { user_id: "driver-02", label: "Мария К.", spend: 295_000, count: 44 },
    ],
    stations: [
      { station_id: "station-01", label: "Лукойл · МКАД", spend: 260_000, count: 38, liters: 3300 },
      { station_id: "station-02", label: "Газпромнефть · Лесная", spend: 210_000, count: 32, liters: 2700 },
    ],
  },
  support: {
    open: 4,
    avg_first_response_minutes: 35,
    avg_resolve_minutes: 240,
  },
};

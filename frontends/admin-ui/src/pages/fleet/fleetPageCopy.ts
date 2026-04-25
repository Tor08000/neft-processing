const rowsLabel = (count: number) => `Rows: ${count}`;

export const fleetCardsPageCopy = {
  title: "Fleet · Cards",
  loading: "Загружаем карты",
  unavailable: "Fleet cards endpoint unavailable in this environment.",
  errors: {
    load: "Не удалось загрузить карты",
  },
  columns: {
    alias: "Alias",
    maskedPan: "Masked PAN",
    status: "Status",
    currency: "Currency",
    issued: "Issued",
    created: "Created",
  },
  filters: {
    status: "Status",
    search: "Search",
    all: "Все",
    searchPlaceholder: "Alias, masked pan, card id",
  },
  actions: {
    reset: "Reset",
  },
  values: {
    fallback: "—",
  },
  footer: {
    rows: rowsLabel,
  },
  empty: {
    title: "Карты не найдены",
    description: "Проверьте фильтры или добавьте новую карту в клиентском кабинете.",
    resetAction: "Reset filters",
  },
} as const;

export const fleetGroupsPageCopy = {
  title: "Fleet · Groups",
  loading: "Загружаем группы",
  unavailable: "Fleet groups endpoint unavailable in this environment.",
  errors: {
    load: "Не удалось загрузить группы",
  },
  columns: {
    group: "Group",
    description: "Description",
    created: "Created",
  },
  values: {
    fallback: "—",
  },
  empty: {
    title: "Группы не найдены",
    description: "Добавьте группы в клиентском кабинете, чтобы управлять доступом к картам.",
  },
} as const;

export const fleetEmployeesPageCopy = {
  title: "Fleet · Employees",
  loading: "Загружаем сотрудников",
  unavailable: "Fleet employees endpoint unavailable in this environment.",
  errors: {
    load: "Не удалось загрузить сотрудников",
  },
  columns: {
    email: "Email",
    status: "Status",
    created: "Created",
  },
  values: {
    fallback: "—",
  },
  empty: {
    title: "Сотрудники не найдены",
    description: "Пригласите сотрудников в клиентском кабинете, чтобы настроить роли доступа.",
  },
} as const;

export const fleetLimitsPageCopy = {
  title: "Fleet · Limits",
  unavailable: "Fleet limits endpoint unavailable in this environment.",
  errors: {
    load: "Не удалось загрузить лимиты",
  },
  columns: {
    scope: "Scope",
    scopeId: "Scope ID",
    period: "Period",
    amount: "Amount",
    volume: "Volume (L)",
    status: "Status",
    effective: "Effective",
    created: "Created",
  },
  filters: {
    scopeType: "Scope type",
    scopeId: "Scope ID",
    select: "Выберите",
    scopePlaceholder: "UUID или ID",
  },
  actions: {
    refresh: "Обновить",
    retry: "Повторить",
  },
  values: {
    fallback: "—",
  },
  footer: {
    rows: rowsLabel,
  },
  empty: {
    missingScopeTitle: "Выберите scope для просмотра лимитов",
    missingScopeDescription: "Укажите тип и идентификатор объекта, чтобы получить активные лимиты.",
    noLimitsTitle: "Лимиты не найдены",
    noLimitsDescription: "Для выбранного scope лимиты отсутствуют.",
  },
} as const;

export const fleetSpendPageCopy = {
  title: "Fleet · Spend",
  loading: "Загружаем расходы",
  unavailable: "Fleet spend endpoint unavailable in this environment.",
  summaryTitle: "Summary",
  transactionsTitle: "Transactions",
  errors: {
    referenceLoad: "Не удалось загрузить справочники",
    spendLoad: "Не удалось загрузить расходы",
  },
  summary: {
    period: "Period",
    amount: "Amount",
    emptyTitle: "Нет данных по расходам",
    emptyDescription: "Проверьте фильтры или выберите другой период.",
  },
  columns: {
    date: "Дата",
    amount: "Сумма",
    cardId: "Card ID",
    merchant: "Merchant",
    category: "Category",
    station: "Station",
  },
  filters: {
    dateFrom: "Date from",
    dateTo: "Date to",
    group: "Group",
    card: "Card",
    groupBy: "Group by",
    all: "Все",
    day: "Day",
    week: "Week",
    month: "Month",
  },
  actions: {
    reset: "Reset",
    refresh: "Обновить",
    retry: "Повторить",
  },
  values: {
    fallback: "—",
  },
  footer: {
    rows: rowsLabel,
  },
  empty: {
    title: "Транзакции не найдены",
    description: "В выбранном периоде нет операций по топливным картам.",
  },
} as const;

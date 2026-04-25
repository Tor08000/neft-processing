const rowsLabel = (count: number) => `Rows: ${count}`;

export const clientsPageCopy = {
  title: "CRM · Clients",
  errors: {
    load: "Не удалось загрузить клиентов",
  },
  columns: {
    clientId: "Client ID",
    legalName: "Legal name",
    status: "Status",
    countryTimezone: "Country/Timezone",
  },
  labels: {
    search: "Search",
    status: "Status",
  },
  placeholders: {
    search: "Search by name/id",
    status: "Status",
  },
  actions: {
    reset: "Reset",
    retry: "Retry",
    create: "Create client",
    close: "Close",
  },
  toasts: {
    created: "Client created",
  },
  footer: {
    rows: rowsLabel,
  },
  empty: {
    filteredTitle: "Clients not found",
    filteredDescription: "Reset filters or broaden the search contour.",
    pristineTitle: "Clients not created yet",
    pristineDescription: "Create the first client to start the CRM contour.",
    resetAction: "Reset filters",
  },
} as const;

export const contractsPageCopy = {
  title: "CRM · Contracts",
  errors: {
    load: "Не удалось загрузить договоры",
    clientIdRequired: "Client ID is required",
  },
  actionLabels: {
    activate: "Activate",
    pause: "Pause",
    terminate: "Terminate",
    apply: "Apply",
  },
  columns: {
    contract: "Contract",
    client: "Client",
    status: "Status",
    valid: "Valid",
    billingMode: "Billing mode",
    currency: "Currency",
    riskProfile: "Risk profile",
    limitProfile: "Limit profile",
    docsRequired: "Docs required",
    actions: "Actions",
  },
  labels: {
    clientId: "Client ID",
    status: "Status",
  },
  placeholders: {
    clientId: "Client ID",
    status: "Status",
  },
  actions: {
    reset: "Reset",
    retry: "Retry",
    create: "Create contract",
    close: "Close",
  },
  values: {
    fallback: "-",
    yes: "Yes",
    no: "No",
  },
  toasts: {
    created: "Contract created",
    done: (action: string) => `${action} done`,
  },
  footer: {
    rows: rowsLabel,
  },
  empty: {
    filteredTitle: "Contracts not found",
    filteredDescription: "Reset the filters or open a wider CRM contour.",
    pristineTitle: "Contracts not created yet",
    pristineDescription: "Create the first contract to unlock lifecycle actions.",
    resetAction: "Reset filters",
  },
  confirm: {
    title: (action: string) => `${action} contract`,
    description: (contractNumber: string) => `Contract ${contractNumber}`,
  },
} as const;

export const subscriptionsPageCopy = {
  title: "CRM · Subscriptions",
  errors: {
    load: "Не удалось загрузить подписки",
    clientIdRequired: "Client ID is required",
  },
  actionLabels: {
    pause: "Pause",
    resume: "Resume",
    cancel: "Cancel",
  },
  columns: {
    subscription: "Subscription",
    client: "Client",
    tariff: "Tariff",
    status: "Status",
    billingDay: "Billing day",
    started: "Started",
    nextRun: "Next run",
    actions: "Actions",
  },
  labels: {
    clientId: "Client ID",
    status: "Status",
  },
  placeholders: {
    clientId: "Client ID",
    status: "Status",
  },
  actions: {
    previewBilling: "Preview billing",
    reset: "Reset",
    retry: "Retry",
    create: "Create subscription",
    close: "Close",
  },
  values: {
    fallback: "-",
  },
  toasts: {
    created: "Subscription created",
    done: (action: string) => `${action} done`,
  },
  footer: {
    rows: rowsLabel,
  },
  empty: {
    filteredTitle: "Subscriptions not found",
    filteredDescription: "Reset filters or change the client contour.",
    pristineTitle: "Subscriptions not created yet",
    pristineDescription: "Create the first subscription to unlock lifecycle operations.",
    resetAction: "Reset filters",
  },
  confirm: {
    title: (action: string) => `${action} subscription`,
    description: (subscriptionId: string) => `Subscription ${subscriptionId}`,
  },
} as const;

export const tariffsPageCopy = {
  title: "CRM · Tariffs",
  errors: {
    load: "Не удалось загрузить тарифы",
  },
  columns: {
    tariffId: "Tariff ID",
    name: "Name",
    status: "Status",
    billingPeriod: "Billing period",
    baseFeeMinor: "Base fee minor",
    features: "Features",
    currency: "Currency",
  },
  actions: {
    retry: "Retry",
    create: "Create tariff",
    close: "Close",
  },
  values: {
    fallback: "-",
  },
  toasts: {
    created: "Tariff created",
  },
  footer: {
    rows: rowsLabel,
  },
  empty: {
    title: "Tariffs not created yet",
    description: "Add the first tariff to unlock the commercial catalogue.",
  },
} as const;

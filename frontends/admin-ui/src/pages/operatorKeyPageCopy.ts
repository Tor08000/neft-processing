export const billingPaymentDetailsCopy = {
  loading: {
    title: "Загружаем платёж",
    description: "Собираем карточку платежа, историю возвратов и audit payload.",
  },
  unavailable: {
    title: "Контур платежей недоступен",
    description: "В этом окружении owner route для карточки платежа не подключён.",
    actionLabel: "К списку платежей",
  },
  loadError: {
    title: "Не удалось загрузить карточку платежа",
    actionLabel: "Повторить",
  },
  notFound: {
    title: "Платёж не найден",
    description: "Откройте платёж из списка, чтобы просмотреть его возвраты и audit payload.",
    actionLabel: "К списку платежей",
  },
  refundsUnavailable: {
    title: "Возвраты временно недоступны",
    description: "История возвратов для этого платежа не была загружена в текущем окружении.",
    actionLabel: "Повторить",
  },
  refundError: {
    title: "Не удалось оформить возврат",
    copyDetailLabel: "Скопировать техническую причину",
  },
} as const;

export const billingPaymentIntakesCopy = {
  rejectPrompt: "Причина отклонения",
} as const;

export const logisticsInspectionCopy = {
  firstUse: {
    title: "Inspection ещё не открыт",
    description:
      "Укажите order_id, чтобы открыть операторский inspection surface без fake summary и без broad logistics dashboard.",
    hint: "После выбора заказа здесь появятся grounded route, ETA, tracking и explain artifacts.",
  },
  loadingLabel: "Загружаем inspection",
  unavailable: {
    title: "Inspection недоступен",
    actionLabel: "Повторить",
  },
  routesEmpty: {
    title: "Маршруты пока не найдены",
    description: "Для этого заказа route version owner ещё не вернул ни одного маршрута.",
  },
  etaEmpty: {
    title: "ETA snapshot отсутствует",
    description:
      "Пока не получен локальный ETA snapshot. После вычисления здесь появится метод, confidence и время расчёта.",
  },
  stopsEmpty: {
    title: "Остановки не найдены",
    description: "Active route ещё не вернул stop list для этого заказа.",
  },
  navigatorEmpty: {
    title: "Navigator snapshot отсутствует",
    description: "Снимок маршрутизатора пока не сохранён. Здесь не будет synthetic fallback.",
  },
  trackingEmpty: {
    title: "Tracking events отсутствуют",
    description:
      "Tracking tail пока пуст. Как только появится событие, секция покажет последний event и vehicle context.",
  },
  explainEmpty: {
    title: "Explain artifacts отсутствуют",
    description: "Navigator explain payloads ещё не сохранены. Мы не подменяем их synthetic drilldown wrappers.",
  },
} as const;

export const casesListCopy = {
  unavailableDescription:
    "Этот owner surface сейчас недоступен в текущем окружении. Мы не подменяем его заглушкой.",
} as const;

export const revenuePageCopy = {
  bucketLabels: {
    all: "Все",
    "0_7": "0–7 дней",
    "8_30": "8–30 дней",
    "31_90": "31–90 дней",
    "90_plus": "90+ дней",
  },
  tableTitles: {
    plan: "План",
    orgs: "Орг.",
    organization: "Организация",
    overdueDays: "Просрочка (дни)",
    amount: "Сумма",
    planStatus: "План/статус",
  },
  states: {
    loadError: "Ошибка загрузки выручки",
    loading: "Загрузка...",
    noData: "Нет данных",
    noOverdues: "Нет просрочек",
    noPlans: "Нет планов",
    noAddons: "Нет add-ons",
  },
} as const;

export const payoutBatchDetailCopy = {
  errors: {
    conflict: "уже отправлено / ref конфликтует",
    invalidState: "нельзя из текущего статуса",
  },
  empty: {
    title: "Нет позиций",
    description: "В этом батче пока нет операций.",
    actionLabel: "Обновить",
  },
} as const;

export const usersPageCopy = {
  header: {
    title: "Администраторы",
    description:
      "Canonical admin roster over the auth-host user registry. Portal shows only admin-capable users.",
    authHostHint: "В auth-host хранятся все пользователи; admin portal управляет только администраторами.",
  },
  errors: {
    loadLog: "Ошибка загрузки администраторов",
    load: "Не удалось загрузить реестр администраторов",
    updateLog: "Не удалось обновить администратора",
    update: "Не удалось обновить администратора",
    loadTitle: "Не удалось загрузить администраторов",
  },
  columns: {
    email: "Email",
    fullName: "Полное имя",
    status: "Статус",
    roles: "Роли",
    created: "Создан",
    actions: "Действия",
  },
  values: {
    fallback: "—",
    active: "Активен",
    disabled: "Выключен",
  },
  actions: {
    edit: "Редактировать",
    add: "Добавить администратора",
    search: "Поиск",
    reset: "Сбросить",
    retry: "Повторить",
    resetFilters: "Сбросить фильтры",
  },
  footer: {
    shown: (visible: number, total: number) => `Показано ${visible} из ${total} администраторов`,
  },
  empty: {
    filteredTitle: "Администраторы не найдены",
    filteredDescription: "Попробуйте изменить фильтр поиска.",
    pristineTitle: "Администраторы отсутствуют",
    pristineDescription: "В реестре пока нет admin-capable пользователей.",
  },
  modal: {
    disableTitle: "Подтвердите отключение администратора",
    enableTitle: "Подтвердите повторное включение администратора",
  },
} as const;

export const createUserPageCopy = {
  header: {
    title: "Создать администратора",
    description:
      "Portal creates only canonical admin-capable users. Client and partner roles are outside this workflow.",
  },
  errors: {
    passwordMismatch: "Пароль и подтверждение не совпадают",
    rolesRequired: "Нужно выбрать хотя бы одну admin role",
    invalidData: "Проверьте корректность введённых данных",
    createFailed: "Не удалось создать администратора",
    createLog: "Ошибка создания администратора",
  },
  labels: {
    email: "Email",
    fullName: "Полное имя",
    password: "Пароль",
    confirmPassword: "Подтверждение пароля",
    roles: "Роли",
  },
  placeholders: {
    email: "admin@neft.local",
    fullName: "Имя администратора",
  },
  actions: {
    submit: "Создать",
    submitting: "Создаём...",
    cancel: "Отмена",
  },
  modal: {
    title: "Подтвердите создание администратора",
  },
} as const;

export const editUserPageCopy = {
  header: {
    title: "Редактирование администратора",
  },
  errors: {
    notFound: "Администратор не найден",
    nonAdmin: "Выбранный пользователь не относится к admin portal contour",
    loadLog: "Не удалось загрузить администратора",
    load: "Не удалось загрузить администратора",
    updateLog: "Ошибка обновления администратора",
    update: "Не удалось сохранить изменения",
    loading: "Загрузка администратора...",
  },
  labels: {
    fullName: "Полное имя",
    active: "Активен",
    roles: "Роли",
  },
  actions: {
    save: "Сохранить",
    cancel: "Отмена",
  },
  audit: {
    title: "Audit activity",
    description: "Canonical audit feed for this admin user.",
    openFull: "Open full audit",
    loading: "Loading audit",
    empty: "No admin-user audit events yet.",
    fallbackTitle: "Audit event",
    chain: "Chain",
    reasonLabel: "Reason",
  },
  modal: {
    title: "Подтвердите изменение администратора",
  },
} as const;

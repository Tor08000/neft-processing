export const adminStatusCopy = {
  loading: {
    title: "Загрузка",
    description: "Проверяем доступ к админ-порталу...",
  },
  unauthorized: {
    title: "Требуется вход",
    description: "Войдите в админ-портал, чтобы продолжить работу.",
    action: "Войти",
  },
  forbidden: {
    description: "У вас нет прав доступа к этому разделу.",
    action: "Вернуться на главную",
  },
  notFound: {
    title: "404 — Страница не найдена",
    description: "Проверьте адрес и попробуйте снова.",
    action: "На главную",
  },
  misconfig: {
    description: "Проверьте настройки роутинга admin API. Ожидаем canonical family `/api/core/v1/admin`.",
    action: "Перейти ко входу",
  },
  crash: {
    title: "Техническая ошибка",
    description: "Произошла непредвиденная ошибка. Попробуйте обновить страницу.",
    homeAction: "На главную",
    refreshAction: "Обновить",
  },
  techError: {
    title: "Техническая ошибка",
    fallbackMessage: "Не удалось загрузить данные админ-портала. Попробуйте позже.",
    homeAction: "На главную",
    refreshAction: "Обновить",
  },
  serviceUnavailable: {
    description: "Сервис временно недоступен. Попробуйте позже.",
    action: "На главную",
  },
} as const;

export const runtimeCenterCopy = {
  subtitle:
    "Операторский обзор платформы: здоровье сервисов, давление очередей, нарушения и критические события без synthetic drilldowns.",
  refresh: {
    idle: "Обновить",
    pending: "Обновляем...",
    loadingLabel: "Загрузка статуса",
  },
  overview: {
    queuePressureClear: "Очереди без застоя",
    openFinanceQueues: "Открыть finance queues",
    openPayouts: "Открыть payouts",
    violationsPresent: "Есть контуры, требующие операторского разбора.",
    violationsClear: "Критичных нарушений не зафиксировано.",
    openAudit: "Открыть audit",
    eventsPresent: "Последние 10 событий доступны для drilldown.",
    eventsClear: "Критических событий сейчас нет.",
  },
  drilldowns: {
    subtitle: "Переходы ведут только в mounted operator owners, без broad generic обходов.",
  },
  health: {
    subtitle: "Статусы сервисов показываем как grounded runtime snapshot, без декоративных графиков.",
  },
  queues: {
    subtitle: "Очереди показывают только реальные backlog/count значения и прямой drilldown по owner route.",
    emptyTitle: "Очереди пусты",
    emptyDescription:
      "Settlement, payout и payment intake queues сейчас без backlog. Когда появится давление, секция покажет count и прямой drilldown.",
    emptyAction: "Открыть finance overview",
  },
  violations: {
    subtitle: "Не показываем broad summary без owner truth: только реальные violation families и top evidence.",
    openAction: "Открыть",
    topEvidenceEmptyTitle: "Top evidence ещё не заполнен",
    topEvidenceEmptyDescription:
      "Нарушения уже зафиксированы, но top-list для этого семейства пока пуст.",
    emptyTitle: "Нарушений не обнаружено",
    emptyDescription:
      "Immutable, invariant и SLA families сейчас не требуют операторского разбора.",
    emptyAction: "Открыть audit",
  },
  degradedEvidence: {
    subtitle: "Здесь остаются только честные warnings и отсутствующие operational tables.",
  },
  events: {
    subtitle: "События связываем с audit correlation, а не оставляем как шумную строку лога.",
    emptyTitle: "Критических событий нет",
    emptyDescription:
      "Когда появятся critical runtime events, здесь будут message, correlation и прямой переход в audit.",
    emptyAction: "Открыть runtime audit",
  },
} as const;

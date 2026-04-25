export const adminDashboardCopy = {
  consoleSubtitle:
    "Строгая операторская панель над mounted admin owners: только реальные очереди, роли, видимость и drilldowns без synthetic widgets.",
  summarySubtitle:
    "Показываем реальную доступность поверхностей и guardrails для текущего admin profile.",
  primaryRoutesSubtitle:
    "Собираем только те маршруты, где у текущего профиля есть реальный смысловой доступ и следующий action.",
  primaryRoutesEmptyTitle: "Нет доступных операторских действий",
  primaryRoutesEmptyDescription:
    "Текущий профиль не имеет mounted admin surfaces с actionable workflow.",
  visibleSurfacesSubtitle:
    "Показываем только mounted canonical operator surfaces. Hidden broad routes сюда не подмешиваются.",
  visibleSurfacesEmptyTitle: "Нет доступных admin surfaces",
  visibleSurfacesEmptyDescription:
    "Для текущего набора ролей не найдено ни одной canonical admin surface.",
} as const;

export const invitationsCopy = {
  status: {
    pending: "Ожидает",
    accepted: "Принято",
    revoked: "Отозвано",
    expired: "Истекло",
  },
} as const;

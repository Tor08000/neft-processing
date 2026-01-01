import type { AchievementBadgeData, StreakData } from "./types";

interface AchievementsResponse {
  badges: AchievementBadgeData[];
  streak: StreakData;
}

export const useAchievements = (): AchievementsResponse => {
  // TODO: заменить мок-данные на API achievements
  const badges: AchievementBadgeData[] = [
    {
      id: "stability",
      icon: "◎",
      title: "Стабильность платежей",
      description: "7 дней без критических отказов",
      status: "unlocked",
    },
    {
      id: "discipline-invoices",
      icon: "SLA",
      title: "Дисциплина счетов",
      description: "Все счета закрыты в срок",
      status: "in-progress",
      progress: 0.8,
    },
    {
      id: "orders-quality",
      icon: "✓",
      title: "Качество заказов",
      description: "95% операций без ручных корректировок",
      status: "unlocked",
    },
  ];

  const streak: StreakData = {
    title: "Серия: 7 дней без ошибок",
    description: "Операции проходят без критических отклонений.",
    totalDays: 7,
    currentDays: 6,
  };

  return { badges, streak };
};

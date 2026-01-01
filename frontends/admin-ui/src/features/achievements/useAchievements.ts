import type { AchievementBadgeData, StreakData } from "./types";

interface AchievementsResponse {
  badges: AchievementBadgeData[];
  streak: StreakData;
}

export const useAchievements = (): AchievementsResponse => {
  // TODO: заменить мок-данные на API achievements
  const badges: AchievementBadgeData[] = [
    {
      id: "discipline-exports",
      icon: "SLA",
      title: "Дисциплина выгрузок",
      description: "95% выгрузок закрыты в SLA за 7 дней",
      status: "unlocked",
    },
    {
      id: "stability-audit",
      icon: "◎",
      title: "Стабильность аудита",
      description: "7 дней без разрывов цепочки",
      status: "in-progress",
      progress: 0.7,
    },
    {
      id: "billing-care",
      icon: "✓",
      title: "Чистый биллинг",
      description: "0 критических ошибок за неделю",
      status: "unlocked",
    },
    {
      id: "payout-control",
      icon: "≡",
      title: "Контроль выплат",
      description: "Без просрочек по партиям выплат",
      status: "locked",
    },
  ];

  const streak: StreakData = {
    title: "Серия: 7 дней без ошибок",
    description: "Финансовые операции без критических инцидентов.",
    totalDays: 7,
    currentDays: 7,
  };

  return { badges, streak };
};

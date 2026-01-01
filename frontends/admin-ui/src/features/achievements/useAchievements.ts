import { useEffect, useMemo, useState } from "react";
import { fetchAchievements } from "./api";
import type { AchievementBadgeData, StreakData } from "./types";

interface AchievementsResponse {
  badges: AchievementBadgeData[];
  streak: StreakData;
}

export const useAchievements = (
  options?: { showToast?: (kind: "success" | "error", text: string) => void },
): AchievementsResponse => {
  const isDev = import.meta.env.DEV;
  const mockData = useMemo<AchievementsResponse>(
    () => ({
      badges: [
        {
          id: "discipline-exports",
          icon: "SLA",
          title: "Дисциплина выгрузок",
          description: "95% выгрузок закрыты в SLA за 7 дней",
          details: "Как получить: держать SLA выгрузок выше 95% в течение 7 дней.",
          status: "unlocked",
        },
        {
          id: "stability-audit",
          icon: "◎",
          title: "Стабильность аудита",
          description: "7 дней без разрывов цепочки",
          details: "Как получить: закрывать аудит без разрывов цепочки 7 дней подряд.",
          status: "in-progress",
          progress: 0.7,
        },
        {
          id: "billing-care",
          icon: "✓",
          title: "Чистый биллинг",
          description: "0 критических ошибок за неделю",
          details: "Как получить: избегать критических ошибок биллинга всю неделю.",
          status: "unlocked",
        },
        {
          id: "payout-control",
          icon: "≡",
          title: "Контроль выплат",
          description: "Без просрочек по партиям выплат",
          details: "Как получить: удерживать просрочки выплат на нуле 14 дней.",
          status: "locked",
        },
      ],
      streak: {
        title: "Серия: 7 дней без ошибок",
        description: "Финансовые операции без критических инцидентов.",
        totalDays: 7,
        currentDays: 7,
      },
    }),
    [],
  );
  const [apiData, setApiData] = useState<AchievementsResponse | null>(null);

  useEffect(() => {
    let active = true;
    fetchAchievements()
      .then((data) => {
        if (active) {
          setApiData(data);
        }
      })
      .catch(() => {
        if (isDev && options?.showToast) {
          options.showToast("error", "Mock mode: Achievements");
        }
      });
    return () => {
      active = false;
    };
  }, [isDev, options?.showToast]);

  return apiData ?? mockData;
};

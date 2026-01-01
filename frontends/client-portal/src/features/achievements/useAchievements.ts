import { useEffect, useMemo, useState } from "react";
import { fetchAchievements } from "./api";
import type { AchievementBadgeData, StreakData } from "./types";

interface AchievementsResponse {
  badges: AchievementBadgeData[];
  streak: StreakData;
}

export const useAchievements = (
  options?: { showToast?: (kind: "success" | "error" | "info", text: string) => void },
): AchievementsResponse => {
  const isDev = import.meta.env.DEV;
  const mockData = useMemo<AchievementsResponse>(
    () => ({
      badges: [
        {
          id: "stability",
          icon: "◎",
          title: "Стабильность платежей",
          description: "7 дней без критических отказов",
          details: "Как получить: поддерживать стабильность платежей без критических отказов 7 дней.",
          status: "unlocked",
        },
        {
          id: "discipline-invoices",
          icon: "SLA",
          title: "Дисциплина счетов",
          description: "Все счета закрыты в срок",
          details: "Как получить: закрывать счета в срок на протяжении 14 дней.",
          status: "in-progress",
          progress: 0.8,
        },
        {
          id: "orders-quality",
          icon: "✓",
          title: "Качество заказов",
          description: "95% операций без ручных корректировок",
          details: "Как получить: держать долю операций без корректировок выше 95% за неделю.",
          status: "unlocked",
        },
      ],
      streak: {
        title: "Серия: 7 дней без ошибок",
        description: "Операции проходят без критических отклонений.",
        totalDays: 7,
        currentDays: 6,
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
          options.showToast("info", "Mock mode: Achievements");
        }
      });
    return () => {
      active = false;
    };
  }, [isDev, options?.showToast]);

  return apiData ?? mockData;
};

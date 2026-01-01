import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchAchievementsSummary } from "./api";
import type { AchievementBadgeData, StreakData } from "./types";

interface AchievementsResponse {
  badges: AchievementBadgeData[];
  streak: StreakData;
  error: string | null;
  isLoading: boolean;
  isMock: boolean;
  reload: () => void;
}

const toastOnce = (key: string, showToast?: (kind: "success" | "error", text: string) => void, text?: string) => {
  if (!showToast || typeof window === "undefined") return;
  try {
    const storageKey = `mock-toast-${key}`;
    if (sessionStorage.getItem(storageKey)) {
      return;
    }
    sessionStorage.setItem(storageKey, "1");
  } catch {
    return;
  }
  showToast("error", text ?? "Mock mode");
};

const mapStatus = (status: string): AchievementBadgeData["status"] => {
  if (status === "unlocked") return "unlocked";
  if (status === "in_progress") return "in-progress";
  return "locked";
};

const resolveIcon = (status: AchievementBadgeData["status"]) => {
  if (status === "unlocked") return "✓";
  if (status === "in-progress") return "◎";
  return "•";
};

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
      error: null,
      isLoading: false,
      isMock: true,
      reload: () => undefined,
    }),
    [],
  );
  const [apiData, setApiData] = useState<AchievementsResponse | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((prev) => prev + 1), []);

  useEffect(() => {
    let active = true;
    setApiData((prev) =>
      prev
        ? { ...prev, isLoading: true, error: null }
        : { badges: [], streak: mockData.streak, error: null, isLoading: true, isMock: false, reload },
    );
    fetchAchievementsSummary()
      .then((data) => {
        if (!active) return;
        const badges = data.badges.map((badge) => {
          const status = mapStatus(badge.status);
          return {
            id: badge.key,
            icon: resolveIcon(status),
            title: badge.title,
            description: badge.description,
            details: badge.how_to ?? undefined,
            status,
            progress: badge.progress ?? undefined,
          };
        });
        const streak = {
          title: data.streak.title,
          description: data.streak.how_to ?? data.streak.title,
          totalDays: data.streak.target,
          currentDays: data.streak.current,
        };
        setApiData({ badges, streak, error: null, isLoading: false, isMock: false, reload });
      })
      .catch((err) => {
        if (!active) return;
        if (isDev) {
          toastOnce("admin-achievements", options?.showToast, "Mock mode: Achievements");
          setApiData({ ...mockData, reload });
          return;
        }
        const message = err instanceof Error ? err.message : "Не удалось загрузить достижения";
        setApiData({ badges: [], streak: mockData.streak, error: message, isLoading: false, isMock: false, reload });
      });
    return () => {
      active = false;
    };
  }, [isDev, mockData, options?.showToast, reload, reloadKey]);

  return apiData ?? mockData;
};

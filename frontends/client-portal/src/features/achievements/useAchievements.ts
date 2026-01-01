import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
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

const isHiddenBadge = (meta: Record<string, unknown> | null | undefined) => {
  if (!meta) return false;
  return Boolean((meta as { hidden?: boolean }).hidden);
};

export const useAchievements = (
  options?: { showToast?: (kind: "success" | "error" | "info", text: string) => void },
): AchievementsResponse => {
  const isDev = import.meta.env.DEV;
  const { user } = useAuth();
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
        history: [true, true, true, true, true, true, false],
        keepText: "Продлится, если операции проходят без критических отклонений.",
        breakText: "Сорвется, если появятся критические отклонения или ручные корректировки.",
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

  const toastOnce = useCallback(
    (key: string, text: string) => {
      if (!options?.showToast || typeof window === "undefined") return;
      try {
        const storageKey = `mock-toast-${key}`;
        if (sessionStorage.getItem(storageKey)) {
          return;
        }
        sessionStorage.setItem(storageKey, "1");
      } catch {
        return;
      }
      options.showToast("info", text);
    },
    [options],
  );

  useEffect(() => {
    let active = true;
    const token = user?.token;
    if (!token) {
      setApiData({ badges: [], streak: mockData.streak, error: "Требуется авторизация", isLoading: false, isMock: false, reload });
      return;
    }
    setApiData((prev) =>
      prev
        ? { ...prev, isLoading: true, error: null }
        : { badges: [], streak: mockData.streak, error: null, isLoading: true, isMock: false, reload },
    );
    fetchAchievementsSummary(token)
      .then((data) => {
        if (!active) return;
        const badges = data.badges.map<AchievementBadgeData | null>((badge) => {
          const status = mapStatus(badge.status);
          if (status === "locked" && isHiddenBadge(badge.meta)) {
            return null;
          }
          return {
            id: badge.key,
            icon: resolveIcon(status),
            title: badge.title,
            description: badge.description,
            details: badge.how_to ?? undefined,
            status,
            progress: badge.progress ?? undefined,
          };
        }).filter((badge): badge is AchievementBadgeData => badge !== null);
        const streak = {
          title: data.streak.title,
          description: data.streak.how_to ?? data.streak.title,
          totalDays: data.streak.target,
          currentDays: data.streak.current,
          history: data.streak.history,
          keepText: "Продлится, если операции проходят без критических отклонений.",
          breakText: "Сорвется, если появятся критические отклонения или ручные корректировки.",
        };
        setApiData({ badges, streak, error: null, isLoading: false, isMock: false, reload });
      })
      .catch((err) => {
        if (!active) return;
        if (isDev) {
          toastOnce("client-achievements", "Mock mode: Achievements");
          setApiData({ ...mockData, reload });
          return;
        }
        const message = err instanceof Error ? err.message : "Не удалось загрузить достижения";
        setApiData({ badges: [], streak: mockData.streak, error: message, isLoading: false, isMock: false, reload });
      });
    return () => {
      active = false;
    };
  }, [isDev, mockData, reload, reloadKey, toastOnce, user?.token]);

  return apiData ?? mockData;
};

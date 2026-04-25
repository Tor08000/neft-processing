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
  const { user } = useAuth();
  const emptyData = useMemo<AchievementsResponse>(
    () => ({
      badges: [],
      streak: {
        title: "Достижения пока не рассчитаны",
        description: "Данные появятся после первой зафиксированной активности.",
        totalDays: 0,
        currentDays: 0,
        history: [],
        keepText: "Серия появится, когда система накопит достаточно событий.",
        breakText: "При критических отклонениях серия будет сброшена.",
      },
      error: null,
      isLoading: false,
      isMock: false,
      reload: () => undefined,
    }),
    [],
  );
  const [apiData, setApiData] = useState<AchievementsResponse | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((prev) => prev + 1), []);

  useEffect(() => {
    let active = true;
    const token = user?.token;
    if (!token) {
      setApiData({ badges: [], streak: emptyData.streak, error: "Требуется авторизация", isLoading: false, isMock: false, reload });
      return;
    }
    setApiData((prev) =>
      prev
        ? { ...prev, isLoading: true, error: null }
        : { badges: [], streak: emptyData.streak, error: null, isLoading: true, isMock: false, reload },
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
        const message = err instanceof Error ? err.message : "Не удалось загрузить достижения";
        if (options?.showToast) {
          options.showToast("error", message);
        }
        setApiData({ badges: [], streak: emptyData.streak, error: message, isLoading: false, isMock: false, reload });
      });
    return () => {
      active = false;
    };
  }, [emptyData, options, reload, reloadKey, user?.token]);

  return apiData ?? emptyData;
};

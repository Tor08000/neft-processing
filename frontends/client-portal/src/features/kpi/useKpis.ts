import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { fetchKpiSummary } from "./api";
import { formatCount, formatDeltaPercent, formatMoney, formatPercent } from "./formatters";
import type { KpiCardData, KpiGoodWhen, KpiHint, KpiStatus, KpiTrend } from "./types";

interface KpiContext {
  summary: unknown;
  operations: unknown[];
  docsAttention: number;
  exportsAttention: number;
  showToast?: (kind: "success" | "error" | "info", text: string) => void;
}

interface KpiResponse {
  kpis: KpiCardData[];
  hints: KpiHint[];
  error: string | null;
  isLoading: boolean;
  isMock: boolean;
  reload: () => void;
}

const EMPTY_KPI_RESPONSE = (reload: () => void, overrides: Partial<KpiResponse> = {}): KpiResponse => ({
  kpis: [],
  hints: [],
  error: null,
  isLoading: false,
  isMock: false,
  reload,
  ...overrides,
});

const resolveStatus = (trend?: KpiTrend, goodWhen: KpiGoodWhen = "neutral", deltaValue?: number): KpiStatus => {
  if (!trend || goodWhen === "neutral") {
    if (deltaValue === undefined) return "neutral";
    if (deltaValue > 0) return "good";
    if (deltaValue < 0) return "bad";
    return "neutral";
  }
  if (goodWhen === "up") return trend === "up" ? "good" : trend === "down" ? "bad" : "neutral";
  if (goodWhen === "down") return trend === "down" ? "good" : trend === "up" ? "bad" : "neutral";
  return "neutral";
};

const resolveStatusByTarget = (
  current: number | undefined,
  target: number | null | undefined,
  goodWhen: KpiGoodWhen,
): KpiStatus | null => {
  if (current === undefined || target === null || target === undefined) return null;
  if (goodWhen === "down") return current <= target ? "good" : "bad";
  if (goodWhen === "up") return current >= target ? "good" : "bad";
  return null;
};

const resolveKpiNudges = (key: string) => {
  if (key.includes("decline")) {
    return { actionLabel: "Посмотреть причины отказов", actionTo: "/analytics/declines", praiseLabel: "Отлично, отказов меньше" };
  }
  if (key.includes("export")) {
    return { actionLabel: "Проверить выгрузки", actionTo: "/analytics/exports", praiseLabel: "Отлично, SLA соблюдается" };
  }
  if (key.includes("invoice") || key.includes("document")) {
    return { actionLabel: "Проверить статус документов", actionTo: "/analytics/documents", praiseLabel: "Документы под контролем" };
  }
  if (key.includes("order")) {
    return { actionLabel: "Посмотреть операции", actionTo: "/analytics/marketplace", praiseLabel: "Отлично, заказы идут по плану" };
  }
  if (key.includes("spend") || key.includes("balance")) {
    return { actionLabel: "Проверить лимиты и бюджет", actionTo: "/analytics/spend", praiseLabel: "Бюджет в норме" };
  }
  return { actionLabel: "Проверить показатель", actionTo: "/analytics/spend", praiseLabel: "Отлично, показатель в норме" };
};

export const useKpis = (_context: KpiContext): KpiResponse => {
  const { user } = useAuth();
  const [apiData, setApiData] = useState<KpiResponse | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((prev) => prev + 1), []);

  useEffect(() => {
    let active = true;
    const token = user?.token;
    if (!token) {
      setApiData(EMPTY_KPI_RESPONSE(reload, { error: "Требуется авторизация" }));
      return;
    }

    setApiData((prev) =>
      prev
        ? { ...prev, error: null, isLoading: true, isMock: false, reload }
        : EMPTY_KPI_RESPONSE(reload, { isLoading: true }),
    );

    fetchKpiSummary(token)
      .then((data) => {
        if (!active) return;
        const kpis = data.kpis.map((item) => {
          const delta = item.delta ?? undefined;
          const trend: KpiTrend | undefined =
            delta === undefined ? undefined : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
          const status =
            resolveStatusByTarget(item.value, item.target ?? undefined, item.good_when) ??
            resolveStatus(trend, item.good_when, delta);
          const nudges = resolveKpiNudges(item.key);

          return {
            id: item.key,
            title: item.title,
            value:
              item.unit === "money"
                ? formatMoney(item.value)
                : item.unit === "percent"
                  ? formatPercent(item.value, 1)
                  : formatCount(item.value),
            current: item.value,
            subvalue: `за ${data.window_days} дней`,
            delta: delta === undefined ? undefined : formatDeltaPercent(delta),
            deltaValue: delta,
            trend,
            goodWhen: item.good_when,
            status,
            ...nudges,
            explainKey: item.key,
            unit: item.unit,
            target: item.target ?? undefined,
            progress: item.progress ?? undefined,
          };
        });

        setApiData({
          kpis,
          hints: [],
          error: null,
          isLoading: false,
          isMock: false,
          reload,
        });
      })
      .catch((err) => {
        if (!active) return;
        const message = err instanceof Error ? err.message : "Не удалось загрузить KPI";
        setApiData(EMPTY_KPI_RESPONSE(reload, { error: message }));
      });

    return () => {
      active = false;
    };
  }, [reload, reloadKey, user?.token]);

  return apiData ?? EMPTY_KPI_RESPONSE(reload, { isLoading: Boolean(user?.token) });
};

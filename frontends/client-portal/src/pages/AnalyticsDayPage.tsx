import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchClientAnalyticsDayDrill } from "../api/clientAnalytics";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { CursorPagination } from "../components/analytics/CursorPagination";
import { DrilldownLayout } from "../components/analytics/DrilldownLayout";
import { MoneyValue } from "../components/common/MoneyValue";
import type { Column } from "../components/common/Table";
import { Table } from "../components/common/Table";
import { AppForbiddenState } from "../components/states";
import { ClientErrorState } from "../components/ClientErrorState";
import { StatusPage } from "../components/StatusPage";
import type { ClientAnalyticsDrillTransaction } from "../types/clientAnalytics";
import { buildDateRange } from "../utils/dateRange";
import { formatDate, formatDateTime, formatLiters } from "../utils/format";
import { hasAnyRole } from "../utils/roles";

interface AnalyticsErrorState {
  status?: number;
}

export function AnalyticsDayPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const dateValue = searchParams.get("date") ?? "";
  const period = searchParams.get("period") ?? "30d";
  const [items, setItems] = useState<ClientAnalyticsDrillTransaction[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<AnalyticsErrorState | null>(null);

  const canAccess = hasAnyRole(user, [
    "CLIENT_OWNER",
    "CLIENT_ADMIN",
    "CLIENT_ACCOUNTANT",
    "CLIENT_FLEET_MANAGER",
  ]);

  const periodLabel = useMemo(() => {
    if (!period) return "—";
    if (period === "custom") return "Пользовательский период";
    if (["7d", "30d", "90d", "mtd"].includes(period)) {
      const range = buildDateRange(period as "7d" | "30d" | "90d" | "mtd");
      return `${formatDate(range.from)} — ${formatDate(range.to)}`;
    }
    return period;
  }, [period]);

  const columns = useMemo<Column<ClientAnalyticsDrillTransaction>[]>(
    () => [
      {
        key: "occurred_at",
        title: "Дата/время",
        render: (row) => formatDateTime(row.occurred_at, user?.timezone),
      },
      {
        key: "card_label",
        title: "Карта",
        render: (row) => row.card_label,
      },
      {
        key: "driver_label",
        title: "Водитель",
        render: (row) => row.driver_label ?? "—",
      },
      {
        key: "station",
        title: "Станция",
        render: (row) => row.station,
      },
      {
        key: "liters",
        title: "Литры",
        render: (row) => formatLiters(row.liters),
      },
      {
        key: "amount",
        title: "Сумма",
        render: (row) => <MoneyValue amount={row.amount} currency={row.currency} />,
        className: "neft-num",
      },
      {
        key: "status",
        title: "Статус",
        render: (row) => row.status,
      },
    ],
    [user?.timezone],
  );

  const loadData = useCallback(
    async (cursor: string | null, append: boolean) => {
      if (!user?.clientId || !dateValue) return;
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      try {
        if (append) {
          setIsLoadingMore(true);
        } else {
          setIsLoading(true);
          setItems([]);
        }
        setError(null);
        const response = await fetchClientAnalyticsDayDrill(user, {
          date: dateValue,
          timezone,
          limit: 50,
          cursor,
        });
        setItems((prev) => (append ? [...prev, ...response.items] : response.items));
        setNextCursor(response.next_cursor);
      } catch (err: unknown) {
        if (err instanceof UnauthorizedError) {
          setError({ status: 401 });
          return;
        }
        if (err instanceof ApiError) {
          setError({ status: err.status });
          return;
        }
        setError({ status: err instanceof ApiError ? err.status : undefined });
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    },
    [dateValue, user],
  );

  useEffect(() => {
    if (!dateValue) return;
    loadData(null, false);
  }, [dateValue, loadData]);

  if (!user || !canAccess) {
    return <AppForbiddenState message="Недостаточно прав для доступа к аналитике." />;
  }

  if (!dateValue) {
    return <StatusPage title="Не указана дата" description="Выберите дату в аналитике и повторите переход." />;
  }

  if (error?.status === 401 || error?.status === 403) {
    return <StatusPage title="Нет доступа" description="У вас нет прав для просмотра этой страницы." />;
  }

  if (error?.status && error.status >= 500) {
    return <StatusPage title="Сервис недоступен" description="Попробуйте обновить страницу позже." />;
  }

  if (error) {
    return (
      <ClientErrorState
        title="Не удалось загрузить операции"
        description="Данные временно недоступны. Попробуйте обновить страницу."
        onRetry={() => void loadData(null, false)}
      />
    );
  }

  return (
    <DrilldownLayout
      title={`Транзакции за ${formatDate(dateValue)}`}
      subtitle="Детализация по выбранному дню."
      periodLabel={periodLabel}
    >
      <Table<ClientAnalyticsDrillTransaction>
        columns={columns}
        data={items}
        loading={isLoading}
        emptyState={{
          title: "Нет данных",
          description: "За выбранный день нет транзакций.",
        }}
      />
      <CursorPagination hasMore={Boolean(nextCursor)} isLoading={isLoadingMore} onLoadMore={() => loadData(nextCursor, true)} />
    </DrilldownLayout>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { fetchClientAnalyticsCardDrill } from "../api/clientAnalytics";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { CursorPagination } from "../components/analytics/CursorPagination";
import { DrilldownLayout } from "../components/analytics/DrilldownLayout";
import { MoneyValue } from "../components/common/MoneyValue";
import type { Column } from "../components/common/Table";
import { Table } from "../components/common/Table";
import { AppForbiddenState } from "../components/states";
import { StatusPage } from "../components/StatusPage";
import type { ClientAnalyticsDrillTransaction } from "../types/clientAnalytics";
import { formatDate, formatDateTime, formatLiters } from "../utils/format";
import { hasAnyRole } from "../utils/roles";

interface AnalyticsErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function AnalyticsCardPage() {
  const { user } = useAuth();
  const { cardId } = useParams();
  const [searchParams] = useSearchParams();
  const dateFrom = searchParams.get("from") ?? "";
  const dateTo = searchParams.get("to") ?? "";
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
    if (!dateFrom || !dateTo) return "—";
    return `${formatDate(dateFrom)} — ${formatDate(dateTo)}`;
  }, [dateFrom, dateTo]);

  const cardLabel = items[0]?.card_label ?? cardId ?? "Карта";

  const columns = useMemo<Column<ClientAnalyticsDrillTransaction>[]>(
    () => [
      {
        key: "occurred_at",
        title: "Дата/время",
        render: (row) => formatDateTime(row.occurred_at, user?.timezone),
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
      if (!user?.clientId || !cardId || !dateFrom || !dateTo) return;
      try {
        if (append) {
          setIsLoadingMore(true);
        } else {
          setIsLoading(true);
          setItems([]);
        }
        setError(null);
        const response = await fetchClientAnalyticsCardDrill(user, cardId, {
          from: dateFrom,
          to: dateTo,
          limit: 50,
          cursor,
        });
        setItems((prev) => (append ? [...prev, ...response.items] : response.items));
        setNextCursor(response.next_cursor);
      } catch (err: unknown) {
        if (err instanceof UnauthorizedError) {
          setError({ message: err.message, status: 401 });
          return;
        }
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : "Не удалось загрузить операции." });
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    },
    [cardId, dateFrom, dateTo, user],
  );

  useEffect(() => {
    if (!cardId || !dateFrom || !dateTo) return;
    loadData(null, false);
  }, [cardId, dateFrom, dateTo, loadData]);

  if (!user || !canAccess) {
    return <AppForbiddenState message="Недостаточно прав для доступа к аналитике." />;
  }

  if (!cardId || !dateFrom || !dateTo) {
    return <StatusPage title="Некорректный период" description="Укажите карту и период для детализации." />;
  }

  if (error?.status === 401 || error?.status === 403) {
    return <StatusPage title="Нет доступа" description="У вас нет прав для просмотра этой страницы." />;
  }

  if (error?.status && error.status >= 500) {
    return <StatusPage title="Сервис недоступен" description="Попробуйте обновить страницу позже." />;
  }

  return (
    <DrilldownLayout
      title={`Транзакции по карте ${cardLabel}`}
      subtitle="Детализация операций по выбранной карте."
      periodLabel={periodLabel}
    >
      <Table<ClientAnalyticsDrillTransaction>
        columns={columns}
        data={items}
        loading={isLoading}
        emptyState={{
          title: "Нет данных",
          description: "За выбранный период транзакции не найдены.",
        }}
        errorState={
          error
            ? {
                title: "Не удалось загрузить операции",
                description: error.message,
                details: error.correlationId ?? undefined,
              }
            : undefined
        }
      />
      <CursorPagination hasMore={Boolean(nextCursor)} isLoading={isLoadingMore} onLoadMore={() => loadData(nextCursor, true)} />
    </DrilldownLayout>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchClientAnalyticsSupportDrill } from "../api/clientAnalytics";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { CursorPagination } from "../components/analytics/CursorPagination";
import { DrilldownLayout } from "../components/analytics/DrilldownLayout";
import type { Column } from "../components/common/Table";
import { Table } from "../components/common/Table";
import { AppForbiddenState } from "../components/states";
import { ClientErrorState } from "../components/ClientErrorState";
import { StatusPage } from "../components/StatusPage";
import type { ClientAnalyticsSupportDrillItem } from "../types/clientAnalytics";
import { formatDate, formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";

interface AnalyticsErrorState {
  status?: number;
}

const FILTER_LABELS: Record<string, string> = {
  open: "Открытые",
  closed: "Закрытые",
  sla_breached: "SLA breached",
  sla_breached_any: "SLA breached (any)",
  sla_breached_first: "SLA breached (first response)",
  sla_breached_resolution: "SLA breached (resolution)",
};

const renderStatusPill = (status: string, variant?: "sla") => {
  const normalized = status.toUpperCase();
  const isSuccess = normalized === "CLOSED" || (variant === "sla" && normalized === "OK");
  const isWarning = normalized === "BREACHED" || normalized === "IN_PROGRESS";
  const className = isSuccess ? "pill pill--success" : isWarning ? "pill pill--warning" : "pill";
  return <span className={className}>{status}</span>;
};

export function AnalyticsSupportPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const dateFrom = searchParams.get("from") ?? "";
  const dateTo = searchParams.get("to") ?? "";
  const filter = searchParams.get("t") ?? "open";
  const [items, setItems] = useState<ClientAnalyticsSupportDrillItem[]>([]);
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

  const columns = useMemo<Column<ClientAnalyticsSupportDrillItem>[]>(
    () => [
      {
        key: "created_at",
        title: "Создан",
        render: (row) => formatDateTime(row.created_at, user?.timezone),
      },
      {
        key: "subject",
        title: "Тикет",
        render: (row) => (
          <div>
            <Link className="link-button" to={`/client/support/${row.ticket_id}`}>
              {row.subject}
            </Link>
            <div className="muted small">{row.ticket_id}</div>
          </div>
        ),
      },
      {
        key: "status",
        title: "Статус",
        render: (row) => renderStatusPill(row.status),
      },
      {
        key: "priority",
        title: "Приоритет",
        render: (row) => row.priority,
      },
      {
        key: "first_response_status",
        title: "SLA (1st)",
        render: (row) => renderStatusPill(row.first_response_status, "sla"),
      },
      {
        key: "resolution_status",
        title: "SLA (resolution)",
        render: (row) => renderStatusPill(row.resolution_status, "sla"),
      },
    ],
    [user?.timezone],
  );

  const loadData = useCallback(
    async (cursor: string | null, append: boolean) => {
      if (!user?.clientId || !dateFrom || !dateTo) return;
      try {
        if (append) {
          setIsLoadingMore(true);
        } else {
          setIsLoading(true);
          setItems([]);
        }
        setError(null);
        const response = await fetchClientAnalyticsSupportDrill(user, {
          from: dateFrom,
          to: dateTo,
          filter,
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
    [dateFrom, dateTo, filter, user],
  );

  useEffect(() => {
    if (!dateFrom || !dateTo) return;
    loadData(null, false);
  }, [dateFrom, dateTo, loadData]);

  if (!user || !canAccess) {
    return <AppForbiddenState message="Недостаточно прав для доступа к аналитике." />;
  }

  if (!dateFrom || !dateTo) {
    return <StatusPage title="Некорректный период" description="Укажите период для детализации." />;
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
        title="Не удалось загрузить тикеты"
        description="Данные временно недоступны. Попробуйте обновить страницу."
        onRetry={() => void loadData(null, false)}
      />
    );
  }

  return (
    <DrilldownLayout
      title="Support drill-down"
      subtitle={`Фильтр: ${FILTER_LABELS[filter] ?? filter}`}
      periodLabel={periodLabel}
    >
      <Table<ClientAnalyticsSupportDrillItem>
        columns={columns}
        data={items}
        loading={isLoading}
        emptyState={{
          title: "Нет данных",
          description: "За выбранный период тикеты не найдены.",
        }}
      />
      <CursorPagination hasMore={Boolean(nextCursor)} isLoading={isLoadingMore} onLoadMore={() => loadData(nextCursor, true)} />
    </DrilldownLayout>
  );
}

import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import type { Column } from "../components/common/Table";
import { Table } from "../components/common/Table";
import { exportAuditEvents, getAuditEvents, type AuditEventSummary, type AuditEventsResponse } from "../api/clientPortal";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";
import { ForbiddenPage } from "./ForbiddenPage";
import { UnauthorizedPage } from "./UnauthorizedPage";
import { StatusPage } from "../components/StatusPage";

const DEFAULT_LIMIT = 50;
const DEBOUNCE_MS = 400;

type AuditFilters = {
  from: string;
  to: string;
  action: string[];
  actor: string;
  entityType: string;
  entityId: string;
  requestId: string;
  limit: number;
};

const ENTITY_TYPE_OPTIONS = [
  { value: "", label: "Все" },
  { value: "card", label: "Card" },
  { value: "card_bulk", label: "Card Bulk" },
  { value: "user", label: "User" },
  { value: "contract", label: "Contract" },
  { value: "document", label: "Document" },
  { value: "limit_template", label: "Limit Template" },
];

const buildFiltersFromSearch = (search: string): AuditFilters => {
  const params = new URLSearchParams(search);
  const limitValue = Number(params.get("limit") ?? DEFAULT_LIMIT);
  return {
    from: params.get("from") ?? "",
    to: params.get("to") ?? "",
    action: params.getAll("action"),
    actor: params.get("actor") ?? "",
    entityType: params.get("entity_type") ?? "",
    entityId: params.get("entity_id") ?? "",
    requestId: params.get("request_id") ?? "",
    limit: Number.isNaN(limitValue) ? DEFAULT_LIMIT : limitValue,
  };
};

const buildSearchFromFilters = (filters: AuditFilters): string => {
  const params = new URLSearchParams();
  if (filters.from) params.set("from", filters.from);
  if (filters.to) params.set("to", filters.to);
  filters.action.forEach((item) => params.append("action", item));
  if (filters.actor) params.set("actor", filters.actor);
  if (filters.entityType) params.set("entity_type", filters.entityType);
  if (filters.entityId) params.set("entity_id", filters.entityId);
  if (filters.requestId) params.set("request_id", filters.requestId);
  if (filters.limit !== DEFAULT_LIMIT) params.set("limit", String(filters.limit));
  const query = params.toString();
  return query ? `?${query}` : "";
};

const formatRelativeTime = (dateStr: string): string => {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return "";
  const diffMs = date.getTime() - Date.now();
  const seconds = Math.round(diffMs / 1000);
  const rtf = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });
  const absSeconds = Math.abs(seconds);
  if (absSeconds < 60) return rtf.format(Math.round(seconds), "second");
  const minutes = Math.round(seconds / 60);
  if (Math.abs(minutes) < 60) return rtf.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return rtf.format(hours, "hour");
  const days = Math.round(hours / 24);
  return rtf.format(days, "day");
};

const getEntityLink = (eventItem: AuditEventSummary): string | null => {
  const entityType = eventItem.entity_type ?? "";
  const entityId = eventItem.entity_id ?? "";
  if (!entityId) return null;
  if (entityType === "card") return `/cards/${entityId}`;
  if (entityType === "card_bulk") return "/cards";
  if (entityType === "limit_template") return "/limits/templates";
  if (entityType === "user" || entityType === "membership") return "/settings/management?tab=users";
  if (["document", "document_acknowledgement", "legal_document", "closing_package"].includes(entityType)) {
    return `/documents/${entityId}`;
  }
  if (["contract", "contract_version", "crm_contract"].includes(entityType)) {
    return `/contracts/${entityId}`;
  }
  if (["invoice", "invoice_thread", "payment", "refund", "credit_note"].includes(entityType)) {
    return `/billing/${entityId}`;
  }
  return null;
};

const buildActorLabel = (eventItem: AuditEventSummary): string => {
  return eventItem.actor_label || eventItem.actor_user_id || "Система";
};

export function AuditPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const location = useLocation();
  const navigate = useNavigate();
  const [filters, setFilters] = useState<AuditFilters>(() => buildFiltersFromSearch(location.search));
  const [debouncedActor, setDebouncedActor] = useState(filters.actor);
  const [debouncedRequestId, setDebouncedRequestId] = useState(filters.requestId);
  const [items, setItems] = useState<AuditEventSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [errorType, setErrorType] = useState<"unauthorized" | "forbidden" | "server" | "unknown" | null>(null);
  const cacheRef = useRef<Map<string, AuditEventsResponse>>(new Map());
  const hasAccess = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"]);

  useEffect(() => {
    const parsed = buildFiltersFromSearch(location.search);
    setFilters(parsed);
    setDebouncedActor(parsed.actor);
    setDebouncedRequestId(parsed.requestId);
  }, [location.search]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedActor(filters.actor), DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [filters.actor]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedRequestId(filters.requestId), DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [filters.requestId]);

  useEffect(() => {
    const search = buildSearchFromFilters(filters);
    if (search !== location.search) {
      navigate({ search }, { replace: true });
    }
  }, [filters, location.search, navigate]);

  const baseFilters = useMemo(
    () => ({
      from: filters.from || undefined,
      to: filters.to || undefined,
      action: filters.action.length ? filters.action : undefined,
      actor: debouncedActor || undefined,
      entity_type: filters.entityType || undefined,
      entity_id: filters.entityId || undefined,
      request_id: debouncedRequestId || undefined,
      limit: filters.limit,
    }),
    [debouncedActor, debouncedRequestId, filters],
  );

  useEffect(() => {
    if (!user || !hasAccess) return;
    const cacheKey = JSON.stringify(baseFilters);
    const cached = cacheRef.current.get(cacheKey);
    if (cached) {
      setItems(cached.items);
      setNextCursor(cached.next_cursor ?? null);
    }
    setIsLoading(true);
    setErrorType(null);
    getAuditEvents(user, baseFilters)
      .then((response) => {
        cacheRef.current.set(cacheKey, response);
        setItems(response.items);
        setNextCursor(response.next_cursor ?? null);
      })
      .catch((err: Error) => {
        if (err instanceof UnauthorizedError) {
          setErrorType("unauthorized");
        } else if (err instanceof ApiError) {
          setErrorType(err.status === 403 ? "forbidden" : err.status >= 500 ? "server" : "unknown");
        } else {
          setErrorType("unknown");
        }
      })
      .finally(() => setIsLoading(false));
  }, [baseFilters, hasAccess, user]);

  const handleLoadMore = async () => {
    if (!user || !nextCursor) return;
    setIsLoadingMore(true);
    setErrorType(null);
    try {
      const response = await getAuditEvents(user, { ...baseFilters, cursor: nextCursor });
      setItems((prev) => [...prev, ...response.items]);
      setNextCursor(response.next_cursor ?? null);
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setErrorType("unauthorized");
      } else if (err instanceof ApiError) {
        setErrorType(err.status === 403 ? "forbidden" : err.status >= 500 ? "server" : "unknown");
      } else {
        setErrorType("unknown");
      }
    } finally {
      setIsLoadingMore(false);
    }
  };

  const handleFilterChange = (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = event.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  const handleActionChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const selected = Array.from(event.target.selectedOptions).map((option) => option.value);
    setFilters((prev) => ({ ...prev, action: selected }));
  };

  const handleClearFilters = () => {
    setFilters({
      from: "",
      to: "",
      action: [],
      actor: "",
      entityType: "",
      entityId: "",
      requestId: "",
      limit: DEFAULT_LIMIT,
    });
  };

  const handleLimitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = Number(event.target.value);
    setFilters((prev) => ({ ...prev, limit: Number.isNaN(value) ? DEFAULT_LIMIT : value }));
  };

  const handleExport = async () => {
    if (!user) return;
    setIsExporting(true);
    try {
      await exportAuditEvents(user, baseFilters);
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setErrorType("unauthorized");
      } else if (err instanceof ApiError) {
        setErrorType(err.status === 403 ? "forbidden" : err.status >= 500 ? "server" : "unknown");
      } else {
        setErrorType("unknown");
      }
    } finally {
      setIsExporting(false);
    }
  };

  const actionOptions = useMemo(() => {
    const set = new Set<string>();
    items.forEach((item) => {
      if (item.action) {
        set.add(item.action);
      }
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [items]);

  const columns: Column<AuditEventSummary>[] = [
    {
      key: "created_at",
      title: t("auditViewer.columns.time"),
      render: (eventItem) => (
        <div className="stack">
          <span>{formatDateTime(eventItem.created_at, user?.timezone)}</span>
          <span className="muted small">{formatRelativeTime(eventItem.created_at)}</span>
        </div>
      ),
    },
    {
      key: "actor",
      title: t("auditViewer.columns.actor"),
      render: (eventItem) => buildActorLabel(eventItem),
    },
    {
      key: "action",
      title: t("auditViewer.columns.action"),
      render: (eventItem) => (
        <div className="stack">
          <span>{eventItem.summary || eventItem.action || "—"}</span>
          <span className="muted small">{eventItem.action ?? "—"}</span>
        </div>
      ),
    },
    {
      key: "entity",
      title: t("auditViewer.columns.entity"),
      render: (eventItem) => {
        const label = eventItem.entity_label || eventItem.entity_id || "—";
        const link = getEntityLink(eventItem);
        return link ? (
          <div className="stack">
            <span>{label}</span>
            <Link className="neft-link" to={link}>
              {t("auditViewer.openObject")}
            </Link>
          </div>
        ) : (
          label
        );
      },
    },
    {
      key: "result",
      title: t("auditViewer.columns.result"),
      render: (eventItem) => eventItem.result ?? "—",
    },
  ];

  if (!hasAccess) {
    return <ForbiddenPage />;
  }

  if (errorType === "unauthorized") {
    return <UnauthorizedPage />;
  }

  if (errorType === "forbidden") {
    return <ForbiddenPage />;
  }

  if (errorType === "server") {
    return <StatusPage title={t("auditViewer.serviceUnavailableTitle")} description={t("auditViewer.serviceUnavailableDescription")} />;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("auditViewer.title")}</h1>
        <div className="actions">
          <button type="button" className="secondary" onClick={handleClearFilters}>
            {t("auditViewer.clearFilters")}
          </button>
          <button type="button" className="secondary" onClick={handleExport} disabled={isExporting}>
            {isExporting ? t("auditViewer.exporting") : t("auditViewer.exportCsv")}
          </button>
        </div>
      </div>
      <div className="card filters">
        <label className="filter">
          <span>{t("auditViewer.filters.from")}</span>
          <input type="datetime-local" name="from" value={filters.from} onChange={handleFilterChange} />
        </label>
        <label className="filter">
          <span>{t("auditViewer.filters.to")}</span>
          <input type="datetime-local" name="to" value={filters.to} onChange={handleFilterChange} />
        </label>
        <label className="filter">
          <span>{t("auditViewer.filters.action")}</span>
          <select multiple value={filters.action} onChange={handleActionChange}>
            {actionOptions.length === 0 ? (
              <option value="" disabled>
                {t("auditViewer.filters.actionEmpty")}
              </option>
            ) : null}
            {actionOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label className="filter">
          <span>{t("auditViewer.filters.actor")}</span>
          <input name="actor" value={filters.actor} onChange={handleFilterChange} placeholder={t("auditViewer.filters.actorPlaceholder")} />
        </label>
        <label className="filter">
          <span>{t("auditViewer.filters.entityType")}</span>
          <select name="entityType" value={filters.entityType} onChange={handleFilterChange}>
            {ENTITY_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="filter">
          <span>{t("auditViewer.filters.entityId")}</span>
          <input name="entityId" value={filters.entityId} onChange={handleFilterChange} placeholder={t("auditViewer.filters.entityIdPlaceholder")} />
        </label>
        <label className="filter">
          <span>{t("auditViewer.filters.requestId")}</span>
          <input
            name="requestId"
            value={filters.requestId}
            onChange={handleFilterChange}
            placeholder={t("auditViewer.filters.requestIdPlaceholder")}
          />
        </label>
        <label className="filter">
          <span>{t("auditViewer.filters.limit")}</span>
          <select name="limit" value={filters.limit} onChange={handleLimitChange}>
            {[25, 50, 100, 200].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Table
        columns={columns}
        data={items}
        loading={isLoading && items.length === 0}
        emptyState={{
          title: t("auditViewer.emptyTitle"),
          description: t("auditViewer.emptyDescription"),
        }}
        errorState={
          errorType === "unknown" && items.length === 0
            ? {
                title: t("auditViewer.loadFailedTitle"),
                description: t("auditViewer.loadFailedDescription"),
              }
            : undefined
        }
      />
      {nextCursor ? (
        <div className="table-footer">
          <button type="button" className="secondary" onClick={handleLoadMore} disabled={isLoadingMore}>
            {isLoadingMore ? t("auditViewer.loadingMore") : t("auditViewer.loadMore")}
          </button>
        </div>
      ) : null}
    </div>
  );
}

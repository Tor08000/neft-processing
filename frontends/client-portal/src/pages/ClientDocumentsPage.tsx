import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { FileText } from "../components/icons";
import { acknowledgeClosingDocument, downloadDocumentFile, fetchDocuments } from "../api/documents";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { ClientErrorState } from "../components/ClientErrorState";
import { DemoEmptyState } from "../components/DemoEmptyState";
import { AppLoadingState } from "../components/states";
import type { ClientDocumentSummary } from "../types/documents";
import { formatDate, formatDateTime } from "../utils/format";
import { MoneyValue } from "../components/common/MoneyValue";
import {
  getDocumentStatusLabel,
  getDocumentStatusTone,
  getDocumentTypeLabel,
  getEdoStatusLabel,
  getEdoTone,
  getSignatureStatusLabel,
  getSignatureTone,
} from "../utils/documents";
import { canAccessFinance } from "../utils/roles";
import { useI18n } from "../i18n";
import { isPwaMode } from "../pwa/mode";
import { isDemoClient } from "@shared/demo/demo";

const DEFAULT_LIMIT = isPwaMode ? 20 : 25;
const LAST_UPDATED_KEY = "pwa:lastUpdated:documents";

export function ClientDocumentsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const location = useLocation();
  const [lastUpdated, setLastUpdated] = useState<string | null>(() => localStorage.getItem(LAST_UPDATED_KEY));
  const [isOffline, setIsOffline] = useState(() => !navigator.onLine);
  const [items, setItems] = useState<ClientDocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    dateFrom: "",
    dateTo: "",
    documentType: "",
    status: "",
    signature: "",
    edoStatus: "",
    requiresAction: "",
    limit: DEFAULT_LIMIT,
  });
  const [offset, setOffset] = useState(0);
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ status?: number } | null>(null);
  const [demoFallback, setDemoFallback] = useState(false);
  const isDemoClientAccount = isDemoClient(user?.email ?? null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedFilters(filters), 450);
    return () => window.clearTimeout(timer);
  }, [filters]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const dateFrom = params.get("from") ?? "";
    const dateTo = params.get("to") ?? "";
    const status = params.get("status") ?? "";
    const signature = params.get("signature") ?? "";
    const edoStatus = params.get("edoStatus") ?? "";
    const requiresAction = params.get("requiresAction") ?? "";
    if (dateFrom || dateTo || status || signature || edoStatus || requiresAction) {
      setFilters((prev) => ({
        ...prev,
        dateFrom,
        dateTo,
        status,
        signature,
        edoStatus,
        requiresAction,
      }));
      setOffset(0);
    }
  }, [location.search]);

  useEffect(() => {
    const handleStatus = () => setIsOffline(!navigator.onLine);
    window.addEventListener("online", handleStatus);
    window.addEventListener("offline", handleStatus);
    return () => {
      window.removeEventListener("online", handleStatus);
      window.removeEventListener("offline", handleStatus);
    };
  }, []);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    setDemoFallback(false);
    fetchDocuments(user, {
      dateFrom: debouncedFilters.dateFrom || undefined,
      dateTo: debouncedFilters.dateTo || undefined,
      documentType: debouncedFilters.documentType || undefined,
      status: debouncedFilters.status || undefined,
      acknowledged:
        debouncedFilters.signature === "signed"
          ? true
          : debouncedFilters.signature === "pending"
            ? false
            : undefined,
      limit: debouncedFilters.limit,
      offset,
    })
      .then((resp) => {
        const filtered =
          debouncedFilters.edoStatus || debouncedFilters.requiresAction
            ? resp.items.filter((item) => {
                const matchesEdo = debouncedFilters.edoStatus
                  ? item.edo_status === debouncedFilters.edoStatus
                  : true;
                const requiresAction =
                  debouncedFilters.requiresAction === "yes"
                    ? item.signature_status !== "signed" ||
                      item.edo_status === "failed" ||
                      item.edo_status === "rejected"
                    : true;
                return matchesEdo && requiresAction;
              })
            : resp.items;
        setItems(filtered);
        setTotal(resp.total);
        const timestamp = new Date().toISOString();
        localStorage.setItem(LAST_UPDATED_KEY, timestamp);
        setLastUpdated(timestamp);
      })
      .catch((err: unknown) => {
        const status = err instanceof ApiError ? err.status : undefined;
        if (isDemoClientAccount && status === 404) {
          setDemoFallback(true);
          setError(null);
          return;
        }
        setError({ status });
      })
      .finally(() => setIsLoading(false));
  }, [debouncedFilters, offset, user, isDemoClientAccount]);

  const handleFilterChange = (evt: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = evt.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
    setOffset(0);
  };

  const handleLimitChange = (evt: ChangeEvent<HTMLSelectElement>) => {
    setFilters((prev) => ({ ...prev, limit: Number(evt.target.value) }));
    setOffset(0);
  };

  const handleDownload = async (documentId: string, fileType: "PDF" | "XLSX") => {
    try {
      await downloadDocumentFile(documentId, fileType, user);
    } catch (err) {
      setError({ status: err instanceof ApiError ? err.status : undefined });
    }
  };

  const handleAck = async (documentId: string) => {
    try {
      await acknowledgeClosingDocument(documentId, user);
      setItems((prev) =>
        prev.map((doc) => (doc.id === documentId ? { ...doc, status: "ACKNOWLEDGED" } : doc)),
      );
    } catch (err) {
      setError({ status: err instanceof ApiError ? err.status : undefined });
    }
  };

  const canAcknowledge = useMemo(() => canAccessFinance(user), [user]);

  const totalRange = useMemo(() => {
    if (total === 0) {
      return "0";
    }
    const from = Math.min(offset + 1, total);
    const to = Math.min(offset + filters.limit, total);
    return `${from}-${to}`;
  }, [filters.limit, offset, total]);

  const documentTypes = useMemo(
    () => [
      { value: "", label: t("documentsPage.filters.all") },
      { value: "INVOICE", label: getDocumentTypeLabel("INVOICE") },
      { value: "ACT", label: getDocumentTypeLabel("ACT") },
      { value: "RECONCILIATION_ACT", label: getDocumentTypeLabel("RECONCILIATION_ACT") },
      { value: "CLOSING_PACKAGE", label: getDocumentTypeLabel("CLOSING_PACKAGE") },
      { value: "OFFER", label: getDocumentTypeLabel("OFFER") },
    ],
    [t],
  );

  const statusTypes = useMemo(
    () => [
      { value: "", label: t("documentsPage.filters.all") },
      { value: "DRAFT", label: getDocumentStatusLabel("DRAFT") },
      { value: "ISSUED", label: getDocumentStatusLabel("ISSUED") },
      { value: "ACKNOWLEDGED", label: getDocumentStatusLabel("ACKNOWLEDGED") },
      { value: "FINALIZED", label: getDocumentStatusLabel("FINALIZED") },
      { value: "VOID", label: getDocumentStatusLabel("VOID") },
    ],
    [t],
  );

  const signatureTypes = useMemo(
    () => [
      { value: "", label: t("documentsPage.filters.all") },
      { value: "signed", label: t("statuses.signature.SIGNED") },
      { value: "pending", label: t("statuses.signature.REQUESTED") },
    ],
    [t],
  );

  const edoTypes = useMemo(
    () => [
      { value: "", label: t("documentsPage.filters.all") },
      { value: "sent", label: t("statuses.edo.SENT") },
      { value: "delivered", label: t("statuses.edo.DELIVERED") },
      { value: "failed", label: t("statuses.edo.FAILED") },
      { value: "rejected", label: t("statuses.edo.REJECTED") },
    ],
    [t],
  );

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>{t("documentsPage.title")}</h2>
          <p className="muted">{t("documentsPage.subtitle")}</p>
          {isOffline && lastUpdated ? (
            <p className="muted small">{t("pwa.offlineStatus", { timestamp: formatDateTime(lastUpdated) })}</p>
          ) : null}
        </div>
      </div>

      <div className="filters">
        <div className="filter">
          <label htmlFor="dateFrom">{t("documentsPage.filters.dateFrom")}</label>
          <input
            id="dateFrom"
            name="dateFrom"
            type="date"
            value={filters.dateFrom}
            onChange={handleFilterChange}
          />
        </div>
        <div className="filter">
          <label htmlFor="dateTo">{t("documentsPage.filters.dateTo")}</label>
          <input id="dateTo" name="dateTo" type="date" value={filters.dateTo} onChange={handleFilterChange} />
        </div>
        <div className="filter">
          <label htmlFor="documentType">{t("documentsPage.filters.documentType")}</label>
          <select id="documentType" name="documentType" value={filters.documentType} onChange={handleFilterChange}>
            {documentTypes.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="status">{t("documentsPage.filters.status")}</label>
          <select id="status" name="status" value={filters.status} onChange={handleFilterChange}>
            {statusTypes.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="signature">{t("documentsPage.filters.signature")}</label>
          <select id="signature" name="signature" value={filters.signature} onChange={handleFilterChange}>
            {signatureTypes.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="edoStatus">{t("documentsPage.filters.edoStatus")}</label>
          <select id="edoStatus" name="edoStatus" value={filters.edoStatus} onChange={handleFilterChange}>
            {edoTypes.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="requiresAction">{t("documentsPage.filters.requiresAction")}</label>
          <select
            id="requiresAction"
            name="requiresAction"
            value={filters.requiresAction}
            onChange={handleFilterChange}
          >
            <option value="">{t("documentsPage.filters.all")}</option>
            <option value="yes">{t("documentsPage.filters.requiresAction")}</option>
          </select>
        </div>
        <div className="filter">
          <label htmlFor="limit">{t("documentsPage.filters.limit")}</label>
          <select id="limit" value={filters.limit} onChange={handleLimitChange}>
            {[25, 50].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? <AppLoadingState /> : null}
      {error ? (
        <ClientErrorState
          title={t("documentsPage.errors.loadFailedTitle")}
          description={t("documentsPage.errors.loadFailedDescription")}
          onRetry={() => setDebouncedFilters((prev) => ({ ...prev }))}
        />
      ) : null}
      {demoFallback ? (
        <DemoEmptyState
          title={t("documentsPage.demo.title")}
          description={t("documentsPage.demo.description")}
          action={
            <Link className="ghost neft-btn-secondary" to="/dashboard">
              {t("documentsPage.demo.action")}
            </Link>
          }
        />
      ) : null}
      {!isLoading && !error && items.length === 0 && !demoFallback ? (
        isDemoClientAccount ? (
          <DemoEmptyState
            title={t("documentsPage.demo.title")}
            description={t("documentsPage.demo.description")}
            action={
              <Link className="ghost neft-btn-secondary" to="/dashboard">
                {t("documentsPage.demo.action")}
              </Link>
            }
          />
        ) : (
          <EmptyState
            icon={<FileText />}
            title={t("emptyStates.documents.title")}
            description={t("emptyStates.documents.description")}
          />
        )
      ) : null}
      {!isLoading && !error && items.length > 0 && !demoFallback ? (
        <>
          {Object.entries(
            items.reduce<Record<string, ClientDocumentSummary[]>>((acc, doc) => {
              const key = doc.period_from ? doc.period_from.slice(0, 7) : t("documentsPage.periodFallback");
              if (!acc[key]) acc[key] = [];
              acc[key].push(doc);
              return acc;
            }, {}),
          ).map(([period, docs]) => (
            <section className="card__section" key={period}>
              <h3>{period}</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>{t("documentsPage.table.type")}</th>
                    <th>{t("documentsPage.table.period")}</th>
                    <th>{t("documentsPage.table.number")}</th>
                    <th>{t("documentsPage.table.amount")}</th>
                    <th>{t("documentsPage.table.lifecycle")}</th>
                    <th>{t("documentsPage.table.sign")}</th>
                    <th>{t("documentsPage.table.edo")}</th>
                    <th>{t("documentsPage.table.updated")}</th>
                    <th>{t("documentsPage.table.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((doc) => (
                    <tr key={doc.id}>
                      <td>{getDocumentTypeLabel(doc.document_type)}</td>
                      <td>
                        {formatDate(doc.period_from)} — {formatDate(doc.period_to)}
                      </td>
                      <td>{doc.number ?? t("common.notAvailable")}</td>
                      <td className="neft-num-cell">
                        {doc.amount ? <MoneyValue amount={doc.amount} currency="RUB" /> : t("common.notAvailable")}
                      </td>
                      <td>
                        <span className={`pill pill--${getDocumentStatusTone(doc.status)}`}>
                          {getDocumentStatusLabel(doc.status)}
                        </span>
                      </td>
                      <td>
                        <span className={`pill pill--${getSignatureTone(doc.signature_status)}`}>
                          {getSignatureStatusLabel(doc.signature_status)}
                        </span>
                      </td>
                      <td>
                        <span className={`pill pill--${getEdoTone(doc.edo_status)}`}>
                          {getEdoStatusLabel(doc.edo_status)}
                        </span>
                      </td>
                      <td>{formatDate(doc.updated_at ?? doc.created_at)}</td>
                      <td>
                        <div className="actions">
                          <Link className="ghost" to={`/client/documents/${doc.id}`}>
                            {t("common.open")}
                          </Link>
                          {doc.status !== "DRAFT" ? (
                            <>
                              <button type="button" className="ghost" onClick={() => handleDownload(doc.id, "PDF")}>
                                PDF
                              </button>
                              <button type="button" className="ghost" onClick={() => handleDownload(doc.id, "XLSX")}>
                                XLSX
                              </button>
                            </>
                          ) : (
                            <span className="muted small">{t("documentsPage.actions.filesUnavailable")}</span>
                          )}
                          {!isPwaMode && canAcknowledge && doc.status === "ISSUED" ? (
                            <button type="button" className="ghost" onClick={() => handleAck(doc.id)}>
                              {t("documentsPage.actions.requestSign")}
                            </button>
                          ) : null}
                          {!isPwaMode && canAcknowledge ? (
                            <button type="button" className="ghost" disabled>
                              {t("documentsPage.actions.resendEdo")}
                            </button>
                          ) : null}
                          {!isPwaMode ? (
                            <button type="button" className="ghost" disabled>
                              {t("documentsPage.actions.viewTimeline")}
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}

          <div className="table-footer">
            <div className="muted">
              {t("documentsPage.footer.shown", { range: totalRange, total })}
            </div>
            <div className="actions">
              <button
                type="button"
                className="ghost"
                disabled={offset === 0}
                onClick={() => setOffset((prev) => Math.max(prev - filters.limit, 0))}
              >
                {t("common.back")}
              </button>
              <button
                type="button"
                className="ghost"
                disabled={offset + filters.limit >= total}
                onClick={() => setOffset((prev) => prev + filters.limit)}
              >
                {t("common.next")}
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FileSpreadsheet } from "../components/icons";
import { fetchExports } from "../api/exports";
import { useAuth } from "../auth/AuthContext";
import { CopyButton } from "../components/CopyButton";
import { Table, type Column } from "../components/common/Table";
import { AppForbiddenState } from "../components/states";
import type { AccountingExportItem } from "../types/exports";
import { formatDate, formatDateTime } from "../utils/format";
import { canAccessFinance } from "../utils/roles";
import { useI18n } from "../i18n";

export function FinanceExportsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [items, setItems] = useState<AccountingExportItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    type: "",
    status: "",
    reconciliation: "",
  });
  const filtersActive = Boolean(filters.type || filters.status || filters.reconciliation);

  const loadExports = useCallback(() => {
    setIsLoading(true);
    setError(null);
    fetchExports(user)
      .then((resp) => setItems(resp.items ?? []))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

  useEffect(() => {
    loadExports();
  }, [loadExports]);

  const filteredItems = useMemo(
    () =>
      items.filter((item) => {
        const matchesType = filters.type ? item.type === filters.type : true;
        const matchesStatus = filters.status ? item.status === filters.status : true;
        const matchesRecon = filters.reconciliation
          ? item.reconciliation_status === filters.reconciliation || item.reconciliation_verdict === filters.reconciliation
          : true;
        return matchesType && matchesStatus && matchesRecon;
      }),
    [filters, items],
  );

  const handleFilterChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const { name, value } = event.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  const columns = useMemo<Column<AccountingExportItem>[]>(
    () => [
      { key: "type", title: t("exportsPage.table.type"), render: (item) => item.type ?? item.title ?? t("common.notAvailable") },
      {
        key: "period",
        title: t("exportsPage.table.period"),
        render: (item) =>
          item.period_from || item.period_to
            ? `${formatDate(item.period_from)} — ${formatDate(item.period_to)}`
            : item.created_at
              ? formatDateTime(item.created_at)
              : t("common.notAvailable"),
      },
      { key: "checksum", title: t("exportsPage.table.checksum"), render: (item) => item.checksum ?? t("common.notAvailable") },
      { key: "mapping", title: t("exportsPage.table.mapping"), render: (item) => item.mapping_version ?? t("common.notAvailable") },
      { key: "status", title: t("exportsPage.table.status"), render: (item) => item.status ?? t("exportsPage.statuses.generated") },
      { key: "erpStatus", title: t("exportsPage.table.erpStatus"), render: (item) => item.erp_status ?? t("common.notAvailable") },
      {
        key: "reconciliation",
        title: t("exportsPage.table.reconciliation"),
        render: (item) => item.reconciliation_status ?? item.reconciliation_verdict ?? t("common.notAvailable"),
      },
      {
        key: "actions",
        title: t("exportsPage.table.actions"),
        render: (item) => (
          <div className="table-row-actions">
            {item.download_url ? (
              <>
                <a className="ghost" href={item.download_url}>
                  {t("actions.download")}
                </a>
                <CopyButton value={item.download_url} label={t("actions.copyLink")} />
              </>
            ) : (
              <span className="muted small">{t("exportsPage.noFile")}</span>
            )}
            {item.id ? (
              <Link className="ghost" to={`/exports/${item.id}`}>
                {t("common.details")}
              </Link>
            ) : null}
          </div>
        ),
      },
    ],
    [t],
  );

  if (!user) {
    return <AppForbiddenState message={t("exportsPage.forbidden.authRequired")} />;
  }

  if (!canAccessFinance(user)) {
    return <AppForbiddenState message={t("exportsPage.forbidden.noAccess")} />;
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>{t("exportsPage.title")}</h2>
          <p className="muted">{t("exportsPage.subtitle")}</p>
        </div>
      </div>
      <Table
        columns={columns}
        data={filteredItems}
        loading={isLoading}
        rowKey={(item) => `${item.id ?? item.type}-${item.download_url ?? item.created_at}`}
        toolbar={
          <div className="table-toolbar">
            <div className="filters">
              <div className="filter">
                <label htmlFor="type">{t("exportsPage.filters.type")}</label>
                <select id="type" name="type" value={filters.type} onChange={handleFilterChange}>
                  <option value="">{t("exportsPage.filters.all")}</option>
                  <option value="CHARGES">{t("exportsPage.types.charges")}</option>
                  <option value="SETTLEMENT">{t("exportsPage.types.settlement")}</option>
                </select>
              </div>
              <div className="filter">
                <label htmlFor="status">{t("exportsPage.filters.status")}</label>
                <select id="status" name="status" value={filters.status} onChange={handleFilterChange}>
                  <option value="">{t("exportsPage.filters.all")}</option>
                  <option value="GENERATED">{t("exportsPage.statuses.generated")}</option>
                  <option value="FAILED">{t("exportsPage.statuses.failed")}</option>
                </select>
              </div>
              <div className="filter">
                <label htmlFor="reconciliation">{t("exportsPage.filters.reconciliation")}</label>
                <select id="reconciliation" name="reconciliation" value={filters.reconciliation} onChange={handleFilterChange}>
                  <option value="">{t("exportsPage.filters.all")}</option>
                  <option value="matched">{t("exportsPage.reconciliation.matched")}</option>
                  <option value="mismatch">{t("exportsPage.reconciliation.mismatch")}</option>
                </select>
              </div>
            </div>
            <div className="toolbar-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => setFilters({ type: "", status: "", reconciliation: "" })}
                disabled={!filtersActive}
              >
                {t("actions.resetFilters")}
              </button>
              <button type="button" className="button secondary" onClick={loadExports}>
                {t("actions.refresh")}
              </button>
            </div>
          </div>
        }
        errorState={
          error
            ? {
                title: t("errors.actionFailedTitle"),
                description: error,
                actionLabel: t("errors.retry"),
                actionOnClick: loadExports,
              }
            : undefined
        }
        footer={<div className="table-footer__content muted">{t("exportsPage.footer.rows", { count: filteredItems.length })}</div>}
        emptyState={{
          icon: <FileSpreadsheet />,
          title: filtersActive ? t("exportsPage.filteredEmpty.title") : t("emptyStates.exports.title"),
          description: filtersActive ? t("exportsPage.filteredEmpty.description") : t("emptyStates.exports.description"),
          actionLabel: filtersActive ? t("actions.resetFilters") : undefined,
          actionOnClick: filtersActive ? () => setFilters({ type: "", status: "", reconciliation: "" }) : undefined,
        }}
      />
    </div>
  );
}

import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FileSpreadsheet } from "../components/icons";
import { fetchExports } from "../api/exports";
import { useAuth } from "../auth/AuthContext";
import { CopyButton } from "../components/CopyButton";
import { EmptyState } from "../components/EmptyState";
import { AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
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

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchExports(user)
      .then((resp) => setItems(resp.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

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

      {isLoading ? <AppLoadingState /> : null}
      {error ? <AppErrorState message={error} /> : null}
      {!isLoading && !error && filteredItems.length === 0 ? (
        <EmptyState
          icon={<FileSpreadsheet />}
          title={t("emptyStates.exports.title")}
          description={t("emptyStates.exports.description")}
        />
      ) : null}
      {!isLoading && !error && filteredItems.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>{t("exportsPage.table.type")}</th>
              <th>{t("exportsPage.table.period")}</th>
              <th>{t("exportsPage.table.checksum")}</th>
              <th>{t("exportsPage.table.mapping")}</th>
              <th>{t("exportsPage.table.status")}</th>
              <th>{t("exportsPage.table.erpStatus")}</th>
              <th>{t("exportsPage.table.reconciliation")}</th>
              <th>{t("exportsPage.table.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item) => (
              <tr key={`${item.id ?? item.type}-${item.download_url ?? item.created_at}`}>
                <td>{item.type ?? item.title ?? t("common.notAvailable")}</td>
                <td>
                  {item.period_from || item.period_to
                    ? `${formatDate(item.period_from)} — ${formatDate(item.period_to)}`
                    : item.created_at
                      ? formatDateTime(item.created_at)
                      : t("common.notAvailable")}
                </td>
                <td>{item.checksum ?? t("common.notAvailable")}</td>
                <td>{item.mapping_version ?? t("common.notAvailable")}</td>
                <td>{item.status ?? t("exportsPage.statuses.generated")}</td>
                <td>{item.erp_status ?? t("common.notAvailable")}</td>
                <td>{item.reconciliation_status ?? item.reconciliation_verdict ?? t("common.notAvailable")}</td>
                <td>
                  <div className="actions">
                    {item.download_url ? (
                      <div className="stack-inline">
                        <a className="ghost" href={item.download_url}>
                          {t("actions.download")}
                        </a>
                        <CopyButton value={item.download_url} label={t("actions.copyLink")} />
                      </div>
                    ) : (
                      <span className="muted small">{t("exportsPage.noFile")}</span>
                    )}
                    {item.id ? (
                      <Link className="ghost" to={`/exports/${item.id}`}>
                        {t("common.details")}
                      </Link>
                    ) : null}
                    <button type="button" className="ghost" disabled>
                      {t("actions.confirmReceived")}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}

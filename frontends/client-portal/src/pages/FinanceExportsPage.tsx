import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchExports } from "../api/exports";
import { useAuth } from "../auth/AuthContext";
import { CopyButton } from "../components/CopyButton";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import type { AccountingExportItem } from "../types/exports";
import { formatDate, formatDateTime } from "../utils/format";
import { canAccessFinance } from "../utils/roles";

export function FinanceExportsPage() {
  const { user } = useAuth();
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
    return <AppForbiddenState message="Требуется авторизация." />;
  }

  if (!canAccessFinance(user)) {
    return <AppForbiddenState message="Недостаточно прав для экспорта и сверок." />;
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Отчеты и выгрузки</h2>
          <p className="muted">Готовые файлы для скачивания и архив документов.</p>
        </div>
      </div>
      <div className="filters">
        <div className="filter">
          <label htmlFor="type">Type</label>
          <select id="type" name="type" value={filters.type} onChange={handleFilterChange}>
            <option value="">Все</option>
            <option value="CHARGES">CHARGES</option>
            <option value="SETTLEMENT">SETTLEMENT</option>
          </select>
        </div>
        <div className="filter">
          <label htmlFor="status">Status</label>
          <select id="status" name="status" value={filters.status} onChange={handleFilterChange}>
            <option value="">Все</option>
            <option value="GENERATED">GENERATED</option>
            <option value="FAILED">FAILED</option>
          </select>
        </div>
        <div className="filter">
          <label htmlFor="reconciliation">Reconciliation</label>
          <select id="reconciliation" name="reconciliation" value={filters.reconciliation} onChange={handleFilterChange}>
            <option value="">Все</option>
            <option value="matched">matched</option>
            <option value="mismatch">mismatch</option>
          </select>
        </div>
      </div>

      {isLoading ? <AppLoadingState /> : null}
      {error ? <AppErrorState message={error} /> : null}
      {!isLoading && !error && filteredItems.length === 0 ? (
        <AppEmptyState title="Отчеты пока не готовы" description="Скоро здесь появятся выгрузки." />
      ) : null}
      {!isLoading && !error && filteredItems.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>Тип</th>
              <th>Период</th>
              <th>Checksum</th>
              <th>Mapping</th>
              <th>Статус</th>
              <th>ERP статус</th>
              <th>Reconciliation</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item) => (
              <tr key={`${item.id ?? item.type}-${item.download_url ?? item.created_at}`}>
                <td>{item.type ?? item.title ?? "—"}</td>
                <td>
                  {item.period_from || item.period_to
                    ? `${formatDate(item.period_from)} — ${formatDate(item.period_to)}`
                    : item.created_at
                      ? formatDateTime(item.created_at)
                      : "—"}
                </td>
                <td>{item.checksum ?? "—"}</td>
                <td>{item.mapping_version ?? "—"}</td>
                <td>{item.status ?? "GENERATED"}</td>
                <td>{item.erp_status ?? "—"}</td>
                <td>{item.reconciliation_status ?? item.reconciliation_verdict ?? "—"}</td>
                <td>
                  <div className="actions">
                    {item.download_url ? (
                      <div className="stack-inline">
                        <a className="ghost" href={item.download_url}>
                          Скачать
                        </a>
                        <CopyButton value={item.download_url} label="Скопировать ссылку" />
                      </div>
                    ) : (
                      <span className="muted small">Нет файла</span>
                    )}
                    {item.id ? (
                      <Link className="ghost" to={`/exports/${item.id}`}>
                        Детали
                      </Link>
                    ) : null}
                    <button type="button" className="ghost" disabled>
                      Confirm received
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

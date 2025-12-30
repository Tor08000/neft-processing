import { useEffect, useState } from "react";
import { fetchExports } from "../api/exports";
import { useAuth } from "../auth/AuthContext";
import { CopyButton } from "../components/CopyButton";
import type { AccountingExportItem } from "../types/exports";
import { formatDate, formatDateTime } from "../utils/format";

export function FinanceExportsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<AccountingExportItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetchExports(user)
      .then((resp) => setItems(resp.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Отчеты и выгрузки</h2>
          <p className="muted">Готовые файлы для скачивания и архив документов.</p>
        </div>
      </div>

      {isLoading ? (
        <div className="skeleton-stack">
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <p className="muted">Отчеты пока не готовы.</p>
          <p className="muted small">Скоро здесь появятся выгрузки по счетам и отчетность.</p>
        </div>
      ) : (
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
            {items.map((item) => (
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
                <td>{item.reconciliation_status ?? "—"}</td>
                <td>
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
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

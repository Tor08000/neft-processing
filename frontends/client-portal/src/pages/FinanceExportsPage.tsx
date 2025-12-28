import { useEffect, useState } from "react";
import { fetchExports } from "../api/exports";
import { useAuth } from "../auth/AuthContext";
import type { ClientExportItem } from "../types/invoices";
import { CopyButton } from "../components/CopyButton";
import { formatDateTime } from "../utils/format";

export function FinanceExportsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ClientExportItem[]>([]);
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
              <th>Документ</th>
              <th>Дата</th>
              <th>Ссылка</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={`${item.type}-${item.download_url}`}>
                <td>{item.title}</td>
                <td>{item.created_at ? formatDateTime(item.created_at) : "—"}</td>
                <td>
                  <div className="stack-inline">
                    <a className="ghost" href={item.download_url}>
                      Скачать
                    </a>
                    <CopyButton value={item.download_url} label="Скопировать ссылку" />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

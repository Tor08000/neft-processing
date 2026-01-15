import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { downloadClientDoc, fetchClientDocsList, type ClientDocItem } from "../api/clientDocs";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { formatDate } from "../utils/format";
import { canAccessFinance } from "../utils/roles";

type ClientDocsListPageProps = {
  title: string;
  docType: string;
};

export function ClientDocsListPage({ title, docType }: ClientDocsListPageProps) {
  const { user } = useAuth();
  const [items, setItems] = useState<ClientDocItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError(null);
    fetchClientDocsList(user, docType)
      .then((resp) => setItems(resp.items ?? []))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [docType, user]);

  if (!canAccessFinance(user)) {
    return <AppForbiddenState message="Недостаточно прав для просмотра документов." />;
  }

  if (loading) {
    return <AppLoadingState label="Загружаем документы..." />;
  }

  if (error) {
    return <AppErrorState message={error} />;
  }

  if (!items.length) {
    return <AppEmptyState title="Документов пока нет" description="Документы появятся после выставления." />;
  }

  const handleDownload = async (documentId: string) => {
    try {
      await downloadClientDoc(documentId, user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось скачать документ.");
    }
  };

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>{title}</h2>
          <p className="muted">Список документов и доступные файлы.</p>
        </div>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Дата</th>
            <th>Статус</th>
            <th>Тип</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{formatDate(item.date)}</td>
              <td>{item.status}</td>
              <td>{item.type}</td>
              <td>
                <button type="button" className="ghost" onClick={() => void handleDownload(item.id)}>
                  Скачать
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { downloadClientDoc, fetchClientDocsList, type ClientDocItem } from "../api/clientDocs";
import { ApiError } from "../api/http";
import { ClientErrorState } from "../components/ClientErrorState";
import { Link } from "react-router-dom";
import { AppEmptyState, AppForbiddenState, AppLoadingState } from "../components/states";
import { Table, type Column } from "../components/common/Table";
import { isDemoClient } from "@shared/demo/demo";
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
  const [error, setError] = useState<{ status?: number } | null>(null);
  const isDemoClientAccount = isDemoClient(user?.email ?? null);

  const loadDocs = () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    fetchClientDocsList(user, docType)
      .then((resp) => setItems(resp.items ?? []))
      .catch((err: unknown) => {
        console.error("Не удалось загрузить документы", err);
        const status = err instanceof ApiError ? err.status : undefined;
        setError({ status });
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDocs();
  }, [docType, user]);

  const handleDownload = async (documentId: string) => {
    try {
      await downloadClientDoc(documentId, user);
    } catch (err) {
      console.error("Не удалось скачать документ", err);
    }
  };

  if (!canAccessFinance(user)) {
    return <AppForbiddenState message="Недостаточно прав для просмотра документов." />;
  }

  if (loading) {
    return <AppLoadingState label="Загружаем документы..." />;
  }

  if (error) {
    return (
      <ClientErrorState
        title="Не удалось загрузить документы"
        description="Документы временно недоступны. Попробуйте обновить страницу."
        onRetry={loadDocs}
        retryLabel="Обновить"
      />
    );
  }

  if (!items.length) {
    if (isDemoClientAccount) {
      return (
        <AppEmptyState
          title="Документы в демо появятся позже"
          description="В рабочем контуре здесь будет архив счетов, актов и договоров."
          action={
            <Link className="ghost neft-btn-secondary" to="/dashboard">
              Перейти в обзор
            </Link>
          }
        />
      );
    }
    return <AppEmptyState title="Документов пока нет" description="Документы появятся после выставления." />;
  }

  const columns: Column<ClientDocItem>[] = [
    {
      key: "date",
      title: "Дата",
      render: (item) => formatDate(item.date),
    },
    {
      key: "status",
      title: "Статус",
      render: (item) => item.status,
    },
    {
      key: "type",
      title: "Тип",
      render: (item) => item.type,
    },
    {
      key: "actions",
      title: "",
      render: (item) => (
        <div className="table-row-actions">
          <button type="button" className="ghost" onClick={() => void handleDownload(item.id)}>
            Скачать
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>{title}</h2>
          <p className="muted">
            {isDemoClientAccount ? "Демонстрационный список документов." : "Список документов и доступные файлы."}
          </p>
        </div>
      </div>
      <Table
        columns={columns}
        data={items}
        rowKey={(item) => item.id}
        footer={<div className="table-footer__content muted">Документов: {items.length}</div>}
      />
    </div>
  );
}

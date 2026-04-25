import { useState } from "react";
import { StatusBadge } from "../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/states";
import type { MarketplaceDocumentDetails } from "../types/marketplace";

interface OrderDocumentsPanelProps {
  documents: MarketplaceDocumentDetails[];
  isLoading: boolean;
  error: string | null;
  correlationId?: string | null;
  canManage: boolean;
  onRefresh: () => void;
}

const FROZEN_PROVIDER_NOTICE =
  "Подпись, отправка в ЭДО и EDO event history заморожены до external provider phase. Документы заказа доступны только для чтения.";

export function OrderDocumentsPanel({
  documents,
  isLoading,
  error,
  correlationId,
  canManage,
  onRefresh,
}: OrderDocumentsPanelProps) {
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const showProviderFrozenNotice = () => {
    setActionMessage(FROZEN_PROVIDER_NOTICE);
  };

  if (isLoading) {
    return <LoadingState label="Загружаем документы заказа..." />;
  }

  if (error) {
    return (
      <ErrorState
        title="Не удалось загрузить документы"
        description={error}
        correlationId={correlationId}
        action={
          <button type="button" className="secondary" onClick={onRefresh}>
            Повторить
          </button>
        }
      />
    );
  }

  if (documents.length === 0) {
    return <EmptyState title="Документы не найдены" description="Для этого заказа пока нет документов." />;
  }

  return (
    <div className="stack">
      {actionMessage ? <div className="notice">{actionMessage}</div> : null}
      <table className="table">
        <thead>
          <tr>
            <th>Тип</th>
            <th>Статус</th>
            <th>Подпись</th>
            <th>ЭДО</th>
            <th>Файл</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id}>
              <td>{doc.type}</td>
              <td>
                <StatusBadge status={doc.status} />
              </td>
              <td>
                <StatusBadge status={doc.signatureStatus ?? "frozen"} />
              </td>
              <td>
                <StatusBadge status={doc.edoStatus ?? "frozen"} />
              </td>
              <td>
                {doc.url ? (
                  <a className="link-button" href={doc.url} target="_blank" rel="noreferrer">
                    Скачать
                  </a>
                ) : (
                  "нет файла"
                )}
              </td>
              <td>
                <div className="stack-inline">
                  <button type="button" className="ghost" onClick={showProviderFrozenNotice}>
                    ЭДО недоступно
                  </button>
                  {canManage ? (
                    <>
                      <button type="button" className="ghost" onClick={showProviderFrozenNotice}>
                        Подпись заморожена
                      </button>
                      <button type="button" className="ghost" onClick={showProviderFrozenNotice}>
                        Отправка в ЭДО заморожена
                      </button>
                    </>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

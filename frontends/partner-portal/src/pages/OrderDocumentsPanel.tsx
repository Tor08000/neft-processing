import { useState } from "react";
import { dispatchDocumentEdo, fetchDocumentEdoEvents, requestDocumentSignature } from "../api/orders";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../components/states";
import type { MarketplaceDocumentDetails, MarketplaceEdoEvent } from "../types/marketplace";
import { formatDateTime } from "../utils/format";

interface OrderDocumentsPanelProps {
  documents: MarketplaceDocumentDetails[];
  isLoading: boolean;
  error: string | null;
  correlationId?: string | null;
  canManage: boolean;
  onRefresh: () => void;
}

export function OrderDocumentsPanel({
  documents,
  isLoading,
  error,
  correlationId,
  canManage,
  onRefresh,
}: OrderDocumentsPanelProps) {
  const { user } = useAuth();
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [edoEvents, setEdoEvents] = useState<MarketplaceEdoEvent[]>([]);
  const [edoLoading, setEdoLoading] = useState(false);
  const [edoError, setEdoError] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<MarketplaceDocumentDetails | null>(null);

  const handleRequestSign = async (documentId: string) => {
    if (!user) return;
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await requestDocumentSignature(user.token, documentId);
      setActionMessage("Запрос на подпись отправлен.");
      onRefresh();
    } catch (err) {
      console.error(err);
      setActionError("Не удалось отправить запрос на подпись.");
    }
  };

  const handleDispatchEdo = async (documentId: string) => {
    if (!user) return;
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await dispatchDocumentEdo(user.token, documentId);
      setActionMessage("ЭДО отправлено.");
      onRefresh();
    } catch (err) {
      console.error(err);
      setActionError("Не удалось отправить документ в ЭДО.");
    }
  };

  const handleOpenEdoEvents = async (document: MarketplaceDocumentDetails) => {
    if (!user) return;
    setSelectedDocument(document);
    setEdoLoading(true);
    setEdoError(null);
    try {
      const events = await fetchDocumentEdoEvents(user.token, document.id);
      setEdoEvents(events);
    } catch (err) {
      console.error(err);
      setEdoError("Не удалось загрузить события ЭДО");
    } finally {
      setEdoLoading(false);
    }
  };

  const handleCloseEdo = () => {
    setSelectedDocument(null);
    setEdoEvents([]);
    setEdoError(null);
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
      {actionError ? <div className="notice error">{actionError}</div> : null}
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
                <StatusBadge status={doc.signatureStatus ?? "—"} />
              </td>
              <td>
                <StatusBadge status={doc.edoStatus ?? "—"} />
              </td>
              <td>
                {doc.url ? (
                  <a className="link-button" href={doc.url} target="_blank" rel="noreferrer">
                    Скачать
                  </a>
                ) : (
                  "—"
                )}
              </td>
              <td>
                <div className="stack-inline">
                  <button type="button" className="ghost" onClick={() => handleOpenEdoEvents(doc)}>
                    ЭДО события
                  </button>
                  {canManage ? (
                    <>
                      <button type="button" className="ghost" onClick={() => handleRequestSign(doc.id)}>
                        Запросить подпись
                      </button>
                      <button type="button" className="ghost" onClick={() => handleDispatchEdo(doc.id)}>
                        Отправить в ЭДО
                      </button>
                    </>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedDocument ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="section-title">
              <h3>ЭДО события: {selectedDocument.type}</h3>
              <button type="button" className="ghost" onClick={handleCloseEdo}>
                Закрыть
              </button>
            </div>
            {edoLoading ? (
              <LoadingState label="Загружаем события ЭДО..." />
            ) : edoError ? (
              <ErrorState
                title="Не удалось загрузить ЭДО события"
                description={edoError}
                action={
                  <button type="button" className="secondary" onClick={() => handleOpenEdoEvents(selectedDocument)}>
                    Повторить
                  </button>
                }
              />
            ) : edoEvents.length === 0 ? (
              <EmptyState title="ЭДО события отсутствуют" description="События ЭДО появятся после отправки." />
            ) : (
              <div className="stack">
                {edoEvents.map((event) => (
                  <div key={event.id} className="invoice-thread__message">
                    <div className="thread-header">
                      <strong>{event.status}</strong>
                      <span className="muted small">{formatDateTime(event.timestamp)}</span>
                    </div>
                    {event.description ? <div>{event.description}</div> : null}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

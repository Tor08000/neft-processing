import { useMemo, useState } from "react";
import { acknowledgeDocument } from "../api/documents";
import { acknowledgeReconciliationRequest } from "../api/reconciliation";
import { createInvoiceMessage } from "../api/invoices";
import { useAuth } from "../auth/AuthContext";

const DOCUMENT_TYPES = [
  { value: "INVOICE_PDF", label: "Invoice PDF" },
  { value: "ACT_RECONCILIATION", label: "Reconciliation act" },
];

export function ActionsPage() {
  const { user } = useAuth();
  const [documentId, setDocumentId] = useState("");
  const [documentType, setDocumentType] = useState(DOCUMENT_TYPES[0].value);
  const [reconciliationId, setReconciliationId] = useState("");
  const [invoiceId, setInvoiceId] = useState("");
  const [supportMessage, setSupportMessage] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canAct = useMemo(() => {
    const roles = user?.roles ?? [];
    return roles.some((role) => ["CLIENT_OWNER", "CLIENT_ACCOUNTANT", "CLIENT_ADMIN"].includes(role));
  }, [user?.roles]);

  const handleAcknowledgeDocument = async () => {
    if (!user) return;
    setError(null);
    setStatus(null);
    try {
      await acknowledgeDocument(documentType, documentId, user);
      setStatus("Документ подтвержден. correlation_id доступен в audit.");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleConfirmExport = async () => {
    if (!user) return;
    setError(null);
    setStatus(null);
    try {
      await acknowledgeReconciliationRequest(reconciliationId, user);
      setStatus("Экспорт подтвержден как полученный.");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleSupportRequest = async () => {
    if (!user) return;
    setError(null);
    setStatus(null);
    try {
      const resp = await createInvoiceMessage(invoiceId, supportMessage, user);
      setStatus(`Запрос отправлен. correlation_id: ${resp.message_id}`);
      setSupportMessage("");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Actions</h2>
            <p className="muted">Безопасные клиентские действия с проверкой ролей и audit.</p>
          </div>
        </div>
        {error ? (
          <div className="card error" role="alert">
            {error}
          </div>
        ) : null}
        {status ? <div className="card success">{status}</div> : null}
      </section>

      <section className="card">
        <h3>Acknowledge document</h3>
        <p className="muted">Подтверждение документа (ack).</p>
        <div className="filters">
          <div className="filter">
            <label htmlFor="documentType">Тип документа</label>
            <select id="documentType" value={documentType} onChange={(e) => setDocumentType(e.target.value)}>
              {DOCUMENT_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div className="filter">
            <label htmlFor="documentId">ID документа</label>
            <input
              id="documentId"
              type="text"
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              placeholder="UUID документа"
            />
          </div>
          <div className="filter">
            <button
              type="button"
              className="primary"
              onClick={() => void handleAcknowledgeDocument()}
              disabled={!documentId || !canAct}
            >
              Подтвердить
            </button>
          </div>
        </div>
        {!canAct ? <p className="muted small">Недостаточно прав для подтверждения документов.</p> : null}
      </section>

      <section className="card">
        <h3>Request e-sign / EDO dispatch</h3>
        <p className="muted">Доступно в read-only режиме. Запрос отправляется через поддержку.</p>
        <div className="actions">
          <button type="button" className="secondary" disabled>
            Запросить подпись
          </button>
          <button type="button" className="secondary" disabled>
            Запросить ЭДО-отправку
          </button>
        </div>
      </section>

      <section className="card">
        <h3>Confirm export received</h3>
        <p className="muted">Подтвердить получение выгрузки/сверки.</p>
        <div className="filters">
          <div className="filter">
            <label htmlFor="reconciliationId">ID сверки</label>
            <input
              id="reconciliationId"
              type="text"
              value={reconciliationId}
              onChange={(e) => setReconciliationId(e.target.value)}
              placeholder="ID запроса сверки"
            />
          </div>
          <div className="filter">
            <button
              type="button"
              className="primary"
              onClick={() => void handleConfirmExport()}
              disabled={!reconciliationId || !canAct}
            >
              Подтвердить получение
            </button>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Create support request</h3>
        <p className="muted">Создать обращение по счету или документу.</p>
        <div className="filters">
          <div className="filter">
            <label htmlFor="invoiceId">Invoice ID</label>
            <input
              id="invoiceId"
              type="text"
              value={invoiceId}
              onChange={(e) => setInvoiceId(e.target.value)}
              placeholder="ID счета"
            />
          </div>
          <div className="filter">
            <label htmlFor="supportMessage">Сообщение</label>
            <textarea
              id="supportMessage"
              value={supportMessage}
              onChange={(e) => setSupportMessage(e.target.value)}
              rows={3}
            />
          </div>
          <div className="filter">
            <button
              type="button"
              className="primary"
              onClick={() => void handleSupportRequest()}
              disabled={!invoiceId || !supportMessage}
            >
              Отправить запрос
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

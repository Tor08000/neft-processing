import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { fetchExports } from "../api/exports";
import { createInvoiceMessage } from "../api/invoices";
import { acknowledgeReconciliationRequest } from "../api/reconciliation";
import { acknowledgeClientDocument, listClientDocuments, type ClientDocumentListItem } from "../api/client/documents";
import { useAuth } from "../auth/AuthContext";
import { Table, type Column } from "../components/common/Table";
import type { AccountingExportItem } from "../types/exports";
import { getAckLikeState, getEdoTone, hasLegacyLikeAttention } from "../utils/clientDocuments";
import { getDocumentTypeLabel, getEdoStatusLabel, getSignatureStatusLabel, getSignatureTone } from "../utils/documents";
import { canAccessFinance } from "../utils/roles";

const ACTIONS_PAGE_DOCUMENT_LIMIT = 50;

function describeCanonicalAction(actionCode: string | null | undefined): string {
  if (actionCode === "SIGN") return "Подписать";
  if (actionCode === "SEND_TO_EDO") return "Отправить";
  if (actionCode === "UPLOAD_OR_SUBMIT") return "Подготовить";
  return "Требует действия";
}

type ActionInboxItem = {
  key: string;
  contour: "document" | "export";
  title: string;
  typeLabel: string;
  attention: ReactNode;
  actionLabel: string;
  href: string;
};

export function ActionsPage() {
  const { user } = useAuth();
  const [documentId, setDocumentId] = useState("");
  const [reconciliationId, setReconciliationId] = useState("");
  const [invoiceId, setInvoiceId] = useState("");
  const [supportMessage, setSupportMessage] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<ClientDocumentListItem[]>([]);
  const [exports, setExports] = useState<AccountingExportItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const canAct = useMemo(() => {
    return canAccessFinance(user);
  }, [user]);

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setLoadError(null);
    Promise.all([
      listClientDocuments({ direction: "inbound", limit: ACTIONS_PAGE_DOCUMENT_LIMIT, offset: 0 }, user),
      listClientDocuments({ direction: "outbound", limit: ACTIONS_PAGE_DOCUMENT_LIMIT, offset: 0 }, user),
      fetchExports(user),
    ])
      .then(([inboundDocs, outboundDocs, exportsResp]) => {
        setDocuments([...(inboundDocs.items ?? []), ...(outboundDocs.items ?? [])]);
        setExports(exportsResp.items ?? []);
      })
      .catch((err: Error) => setLoadError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

  const actionableDocuments = useMemo(() => documents.filter((doc) => hasLegacyLikeAttention(doc)), [documents]);
  const actionableExports = useMemo(
    () => exports.filter((item) => item.reconciliation_status === "mismatch" || item.status === "FAILED"),
    [exports],
  );

  const inboxItems = useMemo<ActionInboxItem[]>(() => {
    const documentItems = actionableDocuments.map((doc) => {
      const ackLikeState = getAckLikeState(doc);
      return {
        key: `document:${doc.id}`,
        contour: "document" as const,
        title: doc.title,
        typeLabel: doc.doc_type ? getDocumentTypeLabel(doc.doc_type) : "—",
        attention: (
          <div className="table-row-actions">
            {ackLikeState ? (
              <span className={`pill pill--${getSignatureTone(ackLikeState)}`}>{getSignatureStatusLabel(ackLikeState)}</span>
            ) : null}
            {doc.edo_status ? (
              <span className={`pill pill--${getEdoTone(doc)}`}>{getEdoStatusLabel(doc.edo_status)}</span>
            ) : null}
            {doc.requires_action ? (
              <span className="pill pill--warning">{describeCanonicalAction(doc.action_code)}</span>
            ) : null}
          </div>
        ),
        actionLabel: doc.requires_action ? describeCanonicalAction(doc.action_code) : "Открыть документ",
        href: `/documents/${doc.id}`,
      };
    });
    const exportItems = actionableExports.map((item) => ({
      key: `export:${item.id ?? item.type ?? ""}`,
      contour: "export" as const,
      title: item.type ?? item.title ?? "—",
      typeLabel: "Экспорт",
      attention: <span className="pill pill--warning">{item.reconciliation_status === "mismatch" ? "Требует сверки" : "Ошибка выгрузки"}</span>,
      actionLabel: item.reconciliation_status === "mismatch" ? "Проверить выгрузку" : "Открыть ошибку",
      href: item.id ? `/exports/${item.id}` : "/exports",
    }));
    return [...documentItems, ...exportItems];
  }, [actionableDocuments, actionableExports]);

  const inboxColumns = useMemo<Column<ActionInboxItem>[]>(
    () => [
      {
        key: "contour",
        title: "Контур",
        render: (item) => (item.contour === "document" ? "Документ" : "Экспорт"),
      },
      {
        key: "title",
        title: "Элемент",
        render: (item) => item.title,
      },
      {
        key: "typeLabel",
        title: "Тип",
        render: (item) => item.typeLabel,
      },
      {
        key: "attention",
        title: "Статус",
        render: (item) => item.attention,
      },
      {
        key: "actionLabel",
        title: "Действие",
        render: (item) => item.actionLabel,
      },
      {
        key: "open",
        title: "",
        render: (item) => (
          <div className="table-row-actions">
            <Link to={item.href}>Открыть</Link>
          </div>
        ),
      },
    ],
    [],
  );

  const handleAcknowledgeDocument = async () => {
    if (!user) return;
    setActionError(null);
    setStatus("queued");
    try {
      await acknowledgeClientDocument(documentId, user);
      setStatus("success: Документ подтвержден. correlation_id доступен в audit.");
    } catch (err) {
      setActionError((err as Error).message);
      setStatus("failed");
    }
  };

  const handleConfirmExport = async () => {
    if (!user) return;
    setActionError(null);
    setStatus("queued");
    try {
      await acknowledgeReconciliationRequest(reconciliationId, user);
      setStatus("success: Экспорт подтвержден как полученный.");
    } catch (err) {
      setActionError((err as Error).message);
      setStatus("failed");
    }
  };

  const handleSupportRequest = async () => {
    if (!user) return;
    setActionError(null);
    setStatus("queued");
    try {
      const resp = await createInvoiceMessage(invoiceId, supportMessage, user);
      setStatus(`success: Запрос отправлен. correlation_id: ${resp.message_id}`);
      setSupportMessage("");
    } catch (err) {
      setActionError((err as Error).message);
      setStatus("failed");
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
        {actionError ? <div className="card error">{actionError}</div> : null}
        {status ? <div className="card success">{status}</div> : null}
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h3>Inbox</h3>
            <p className="muted">Все элементы, требующие действий, в одном списке.</p>
          </div>
        </div>
        <Table
          columns={inboxColumns}
          data={inboxItems}
          loading={isLoading}
          rowKey={(item) => item.key}
          errorState={
            loadError
              ? {
                  title: "Не удалось загрузить inbox действий",
                  description: loadError,
                }
              : undefined
          }
          emptyState={{
            title: "Ничего не требует действий",
            description: "Когда появятся документы или выгрузки с action-required статусом, они будут показаны здесь.",
          }}
          footer={loadError ? null : <div className="table-footer__content muted">Элементов inbox: {inboxItems.length}</div>}
        />
      </section>

      <section className="card">
        <h3>Acknowledge closing document</h3>
        <p className="muted">Подтверждение closing-документа (ack).</p>
        <div className="filters">
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
          <Link className="secondary" to="/client/support/new?topic=document_signature">
            Запросить подпись
          </Link>
          <Link className="secondary" to="/client/support/new?topic=document_edo">
            Запросить ЭДО-отправку
          </Link>
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

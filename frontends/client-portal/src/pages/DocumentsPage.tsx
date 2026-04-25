import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createOutboundDocument, listClientDocuments, type ClientDocumentsDirection } from "../api/client/documents";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import {
  formatPeriodGroupLabel,
  getAckLikeState,
  getEdoTone,
  getPeriodGroupKey,
  hasLegacyLikeAttention,
} from "../utils/clientDocuments";
import { getDocumentTypeLabel, getEdoStatusLabel, getSignatureStatusLabel, getSignatureTone } from "../utils/documents";
import { formatDate } from "../utils/format";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";

const PAGE_LIMIT = 20;

type AttentionFilter = "" | "attention";

function describeCanonicalAction(actionCode: string | null | undefined): string {
  if (actionCode === "SIGN") return "Подписать";
  if (actionCode === "SEND_TO_EDO") return "Отправить";
  if (actionCode === "UPLOAD_OR_SUBMIT") return "Подготовить";
  return "Требует действия";
}

function formatPeriodRange(periodFrom: string | null | undefined, periodTo: string | null | undefined): string {
  if (!periodFrom && !periodTo) return "—";
  return `${formatDate(periodFrom)} — ${formatDate(periodTo)}`;
}

export function DocumentsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [direction, setDirection] = useState<ClientDocumentsDirection>("inbound");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [attentionFilter, setAttentionFilter] = useState<AttentionFilter>("");
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState<{ status?: number; code?: string } | null>(null);
  const [data, setData] = useState({ items: [], total: 0, limit: PAGE_LIMIT, offset: 0 } as Awaited<
    ReturnType<typeof listClientDocuments>
  >);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("ACT");
  const [description, setDescription] = useState("");

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    listClientDocuments({ direction, status: status || undefined, q: q || undefined, limit: PAGE_LIMIT, offset }, user)
      .then((response) => {
        if (!active) return;
        setData(response);
      })
      .catch((err: unknown) => {
        if (!active) return;
        if (err instanceof UnauthorizedError || (err instanceof ApiError && err.status === 401)) {
          navigate("/login", { replace: true });
          return;
        }
        if (err instanceof ApiError) {
          setError({ status: err.status, code: err.code ?? undefined });
          return;
        }
        setError({});
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [direction, status, q, offset, navigate, user, reloadKey]);

  const visibleItems = useMemo(
    () => (attentionFilter === "attention" ? data.items.filter((item) => hasLegacyLikeAttention(item)) : data.items),
    [attentionFilter, data.items],
  );

  const groupedItems = useMemo(
    () =>
      Object.entries(
        visibleItems.reduce<Record<string, typeof data.items>>((acc, item) => {
          const groupKey = getPeriodGroupKey(item);
          if (!acc[groupKey]) acc[groupKey] = [];
          acc[groupKey].push(item);
          return acc;
        }, {}),
      ),
    [visibleItems],
  );

  const hasPrev = offset > 0;
  const hasNext = useMemo(() => offset + PAGE_LIMIT < data.total, [data.total, offset]);
  const hasActiveFilters = Boolean(status || q || attentionFilter);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    const created = await createOutboundDocument(
      { title, doc_type: docType || undefined, description: description || undefined },
      user,
    );
    setIsCreateOpen(false);
    navigate(`/client/documents/${created.id}`);
  };

  const footerText = useMemo(() => {
    if (attentionFilter === "attention") {
      return `Требуют внимания на странице: ${visibleItems.length}`;
    }
    if (data.total === 0) {
      return "Показано 0";
    }
    const from = Math.min(offset + 1, data.total);
    const to = Math.min(offset + PAGE_LIMIT, data.total);
    return `Показано ${from}-${to} из ${data.total}`;
  }, [attentionFilter, data.total, offset, visibleItems.length]);

  const resetFilters = () => {
    setStatus("");
    setQ("");
    setAttentionFilter("");
    setOffset(0);
  };

  const renderEmptyAction = () => {
    if (hasActiveFilters || offset > 0) {
      return (
        <div className="actions">
          <button type="button" className="secondary" onClick={resetFilters}>
            Сбросить фильтры
          </button>
        </div>
      );
    }
    if (direction === "outbound") {
      return (
        <div className="actions">
          <button type="button" className="secondary" onClick={() => setIsCreateOpen(true)}>
            Создать документ
          </button>
        </div>
      );
    }
    return (
      <div className="actions">
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setDirection("outbound");
            setOffset(0);
          }}
        >
          Открыть исходящие
        </button>
      </div>
    );
  };

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h1>Документы</h1>
          <p className="muted">
            Canonical client document flow с явным разделением на входящие и исходящие документы, без возврата в legacy detail tail.
          </p>
        </div>
        <div className="toolbar-actions">
          <button
            type="button"
            className={direction === "inbound" ? "neft-button neft-btn-primary" : "ghost"}
            onClick={() => {
              setDirection("inbound");
              setOffset(0);
            }}
          >
            Входящие
          </button>
          <button
            type="button"
            className={direction === "outbound" ? "neft-button neft-btn-primary" : "ghost"}
            onClick={() => {
              setDirection("outbound");
              setOffset(0);
            }}
          >
            Исходящие
          </button>
          {direction === "outbound" ? (
            <button type="button" className="secondary" onClick={() => setIsCreateOpen((value) => !value)}>
              {isCreateOpen ? "Скрыть форму" : "Создать документ"}
            </button>
          ) : null}
        </div>
      </div>

      {isCreateOpen ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h2>Новый исходящий документ</h2>
              <p className="muted">Создание доступно только в canonical outbound contour.</p>
            </div>
          </div>
          <form onSubmit={handleCreate} className="stack">
            <input value={title} minLength={3} maxLength={200} required onChange={(e) => setTitle(e.target.value)} placeholder="Название" />
            <select value={docType} onChange={(e) => setDocType(e.target.value)}>
              <option value="ACT">ACT</option>
              <option value="INVOICE">INVOICE</option>
              <option value="LETTER">LETTER</option>
              <option value="OTHER">OTHER</option>
            </select>
            <textarea value={description} maxLength={2000} onChange={(e) => setDescription(e.target.value)} placeholder="Описание" />
            <div className="stack-inline">
              <button type="submit" className="secondary">
                Создать
              </button>
              <button type="button" className="ghost" onClick={() => setIsCreateOpen(false)}>
                Отмена
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <section className="card">
        <div className="surface-toolbar">
          <div className="table-toolbar__content">
            <div className="filters">
              <label className="filter">
                Поиск
                <input
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setOffset(0);
                  }}
                  placeholder="Поиск"
                />
              </label>
              <label className="filter">
                Статус
                <select
                  value={status}
                  onChange={(e) => {
                    setStatus(e.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">Все статусы</option>
                  <option value="DRAFT">DRAFT</option>
                  <option value="SENT">SENT</option>
                  <option value="RECEIVED">RECEIVED</option>
                  <option value="SIGNED">SIGNED</option>
                  <option value="REJECTED">REJECTED</option>
                  <option value="CANCELLED">CANCELLED</option>
                </select>
              </label>
              <label className="filter">
                Внимание
                <select
                  value={attentionFilter}
                  onChange={(e) => {
                    setAttentionFilter(e.target.value as AttentionFilter);
                    setOffset(0);
                  }}
                >
                  <option value="">Все документы</option>
                  <option value="attention">Требуют внимания</option>
                </select>
              </label>
            </div>
          </div>
        </div>

        {isLoading ? <AppLoadingState label="Загружаем документы..." /> : null}
        {!isLoading && error ? (
          <AppErrorState
            message="Не удалось загрузить документы. Проверьте фильтры или попробуйте обновить список ещё раз."
            status={error.status}
            onRetry={() => setReloadKey((value) => value + 1)}
          />
        ) : null}

        {!isLoading && !error && groupedItems.length === 0 ? (
          <AppEmptyState
            title={hasActiveFilters ? "Документы не найдены" : direction === "outbound" ? "Исходящих документов пока нет" : "Документы пока не появились"}
            description={
              hasActiveFilters
                ? "Фильтры слишком узкие для текущего набора документов. Сбросьте их, чтобы вернуться к полной выдаче."
                : direction === "outbound"
                  ? "Когда вы создадите исходящий документ, он появится в этой ленте вместе со статусом подготовки и отправки."
                  : "Как только появятся входящие документы или closing packages, они отобразятся в этом canonical list surface."
            }
            action={renderEmptyAction()}
          />
        ) : null}

        {!isLoading && !error && groupedItems.length > 0 ? (
          <div className="stack">
            {groupedItems.map(([groupKey, items]) => (
              <section key={groupKey} className="card">
                <div className="card__header">
                  <div>
                    <h3>{formatPeriodGroupLabel(groupKey)}</h3>
                    <p className="muted">Периодическая группировка остаётся read-only convenience layer и не меняет canonical document ownership.</p>
                  </div>
                </div>
                <div className="table-shell">
                  <div className="table-scroll">
                    <table className="table neft-table">
                      <thead>
                        <tr>
                          <th>Название</th>
                          <th>Тип</th>
                          <th>Период</th>
                          <th>Статус</th>
                          <th>Внимание</th>
                          <th>Подпись</th>
                          <th>ЭДО</th>
                          <th>Action</th>
                          <th>Файлов</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((item) => {
                          const ackLikeState = getAckLikeState(item);
                          const hasAttention = hasLegacyLikeAttention(item);
                          return (
                            <tr key={item.id} onClick={() => navigate(`/client/documents/${item.id}`)} style={{ cursor: "pointer" }}>
                              <td>{item.title}</td>
                              <td>{item.doc_type ? getDocumentTypeLabel(item.doc_type) : "—"}</td>
                              <td>{formatPeriodRange(item.period_from, item.period_to)}</td>
                              <td>{item.status}</td>
                              <td>{hasAttention ? <span className="pill pill--warning">Требует внимания</span> : "—"}</td>
                              <td>
                                {ackLikeState ? (
                                  <span className={`pill pill--${getSignatureTone(ackLikeState)}`}>
                                    {getSignatureStatusLabel(ackLikeState)}
                                  </span>
                                ) : (
                                  "—"
                                )}
                              </td>
                              <td>
                                {item.edo_status ? (
                                  <span className={`pill pill--${getEdoTone(item)}`}>{getEdoStatusLabel(item.edo_status)}</span>
                                ) : (
                                  "—"
                                )}
                              </td>
                              <td>{item.requires_action ? describeCanonicalAction(item.action_code) : "-"}</td>
                              <td>{item.files_count}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </section>
            ))}

            <div className="table-footer">
              <div className="table-footer__content">
                <span>{footerText}</span>
                <div className="toolbar-actions">
                  <button type="button" className="ghost" onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_LIMIT))} disabled={!hasPrev}>
                    Назад
                  </button>
                  <button type="button" className="ghost" onClick={() => setOffset((prev) => prev + PAGE_LIMIT)} disabled={!hasNext}>
                    Вперёд
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

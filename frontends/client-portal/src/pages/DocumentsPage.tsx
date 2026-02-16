import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listClientDocuments, type ClientDocumentsDirection } from "../api/client/documents";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "../auth/AuthContext";

const PAGE_LIMIT = 20;

export function DocumentsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [direction, setDirection] = useState<ClientDocumentsDirection>("inbound");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ status?: number; code?: string } | null>(null);
  const [data, setData] = useState({ items: [], total: 0, limit: PAGE_LIMIT, offset: 0 } as Awaited<
    ReturnType<typeof listClientDocuments>
  >);

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
  }, [direction, status, q, offset, navigate, user]);

  const hasPrev = offset > 0;
  const hasNext = useMemo(() => offset + PAGE_LIMIT < data.total, [data.total, offset]);

  return (
    <div className="card">
      <h2>Документы</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button type="button" className={direction === "inbound" ? "btn" : "ghost"} onClick={() => { setDirection("inbound"); setOffset(0); }}>
          Входящие
        </button>
        <button type="button" className={direction === "outbound" ? "btn" : "ghost"} onClick={() => { setDirection("outbound"); setOffset(0); }}>
          Исходящие
        </button>
      </div>

      <div className="filters" style={{ marginBottom: 12 }}>
        <input value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} placeholder="Поиск по названию/номеру/контрагенту" />
        <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
          <option value="">Все статусы</option>
          <option value="DRAFT">DRAFT</option>
          <option value="SENT">SENT</option>
          <option value="RECEIVED">RECEIVED</option>
          <option value="SIGNED">SIGNED</option>
          <option value="REJECTED">REJECTED</option>
          <option value="CANCELLED">CANCELLED</option>
        </select>
      </div>

      {error?.status === 403 && error.code === "client_not_bound" ? (
        <div className="card">Аккаунт клиента не активирован</div>
      ) : null}
      {error?.status && error.status >= 500 ? <div className="card">Не удалось загрузить документы.</div> : null}

      {isLoading ? <p>Загрузка…</p> : null}

      {!isLoading && !error?.status && data.items.length === 0 ? (
        <div className="card">
          <h3>Документов пока нет</h3>
          <p className="muted">Когда появятся входящие или исходящие документы, вы увидите их здесь.</p>
        </div>
      ) : null}

      {!isLoading && data.items.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Тип</th>
              <th>Статус</th>
              <th>Контрагент</th>
              <th>Номер</th>
              <th>Дата</th>
              <th>Файлов</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <tr key={item.id}>
                <td>{item.title}</td>
                <td>{item.doc_type ?? "—"}</td>
                <td>{item.status}</td>
                <td>{item.counterparty_name ?? "—"}</td>
                <td>{item.number ?? "—"}</td>
                <td>{item.date ?? "—"}</td>
                <td>{item.files_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button type="button" onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_LIMIT))} disabled={!hasPrev}>
          Назад
        </button>
        <button type="button" onClick={() => setOffset((prev) => prev + PAGE_LIMIT)} disabled={!hasNext}>
          Вперёд
        </button>
      </div>
    </div>
  );
}

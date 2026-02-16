import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createOutboundDocument, listClientDocuments, type ClientDocumentsDirection } from "../api/client/documents";
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
  }, [direction, status, q, offset, navigate, user]);

  const hasPrev = offset > 0;
  const hasNext = useMemo(() => offset + PAGE_LIMIT < data.total, [data.total, offset]);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    const created = await createOutboundDocument(
      { title, doc_type: docType || undefined, description: description || undefined },
      user,
    );
    setIsCreateOpen(false);
    navigate(`/client/documents/${created.id}`);
  };

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
        {direction === "outbound" ? <button type="button" onClick={() => setIsCreateOpen((v) => !v)}>Создать документ</button> : null}
      </div>

      {isCreateOpen ? (
        <form onSubmit={handleCreate} style={{ marginBottom: 12, display: "grid", gap: 8 }}>
          <input value={title} minLength={3} maxLength={200} required onChange={(e) => setTitle(e.target.value)} placeholder="Название" />
          <select value={docType} onChange={(e) => setDocType(e.target.value)}>
            <option value="ACT">ACT</option>
            <option value="INVOICE">INVOICE</option>
            <option value="LETTER">LETTER</option>
            <option value="OTHER">OTHER</option>
          </select>
          <textarea value={description} maxLength={2000} onChange={(e) => setDescription(e.target.value)} placeholder="Описание" />
          <button type="submit">Создать</button>
        </form>
      ) : null}

      <div className="filters" style={{ marginBottom: 12 }}>
        <input value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} placeholder="Поиск" />
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

      {isLoading ? <p>Загрузка…</p> : null}

      {!isLoading && data.items.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Тип</th>
              <th>Статус</th>
              <th>Файлов</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <tr key={item.id} onClick={() => navigate(`/client/documents/${item.id}`)} style={{ cursor: "pointer" }}>
                <td>{item.title}</td>
                <td>{item.doc_type ?? "—"}</td>
                <td>{item.status}</td>
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

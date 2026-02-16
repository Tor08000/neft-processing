import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { downloadClientDocumentFile, getClientDocument, uploadClientDocumentFile, type ClientDocumentDetails } from "../api/client/documents";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";

function formatSize(size: number): string {
  if (size > 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  if (size > 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size} B`;
}

export function ClientDocumentDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [document, setDocument] = useState<ClientDocumentDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorCode, setErrorCode] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getClientDocument(id, user)
      .then((d) => {
        setDocument(d);
        setErrorCode(null);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          if (err.status === 401) {
            navigate("/login", { replace: true });
            return;
          }
          setErrorCode(err.status);
          return;
        }
        setErrorCode(500);
      })
      .finally(() => setLoading(false));
  }, [id, user, navigate]);

  const onUpload = async (file: File | null) => {
    if (!file || !id) return;
    setUploading(true);
    try {
      const created = await uploadClientDocumentFile(id, file, user);
      setDocument((prev) => (prev ? { ...prev, files: [created, ...prev.files] } : prev));
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorCode(err.status);
      } else {
        setErrorCode(500);
      }
    } finally {
      setUploading(false);
    }
  };

  if (!id) return <div className="card">Документ не найден</div>;
  if (loading) return <div className="card">Загрузка…</div>;
  if (errorCode === 404) return <div className="card">Документ не найден</div>;
  if (errorCode) return <div className="card">Не удалось загрузить документ</div>;
  if (!document) return <div className="card">Документ не найден</div>;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h2>{document.title}</h2>
        <Link to="/client/documents">Назад</Link>
      </div>
      <p>Направление: {document.direction}</p>
      <p>Статус: {document.status}</p>
      <p>Тип: {document.doc_type ?? "—"}</p>
      <p>Описание: {document.description ?? "—"}</p>

      <div style={{ margin: "12px 0" }}>
        <label htmlFor="file-upload">Загрузить файл</label>
        <input
          id="file-upload"
          type="file"
          onChange={(e) => void onUpload(e.target.files?.[0] ?? null)}
          disabled={uploading}
        />
        {uploading ? <p>Загрузка файла…</p> : null}
      </div>

      <table>
        <thead>
          <tr>
            <th>Файл</th>
            <th>Размер</th>
            <th>Создан</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {document.files.map((file) => (
            <tr key={file.id}>
              <td>{file.filename}</td>
              <td>{formatSize(file.size)}</td>
              <td>{new Date(file.created_at).toLocaleString()}</td>
              <td>
                <button type="button" onClick={() => void downloadClientDocumentFile(file.id, user)}>Download</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

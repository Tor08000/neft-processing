import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useLegalGate } from "../auth/LegalGateContext";
import { formatDateTime } from "../utils/format";

export function LegalPage() {
  const { user } = useAuth();
  const { required, isBlocked, isLoading, errorMessage, document, loadDocument, accept, refresh, accessState } = useLegalGate();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);

  const isAccessBlocked = accessState === "unauthorized" || accessState === "forbidden" || accessState === "stopped";

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!selectedCode) return;
    const item = required.find((doc) => doc.code === selectedCode);
    if (!item) return;
    void loadDocument(item.code, item.required_version, item.locale);
  }, [loadDocument, required, selectedCode]);

  const selected = useMemo(() => {
    if (!selectedCode) return null;
    return required.find((doc) => doc.code === selectedCode) ?? null;
  }, [required, selectedCode]);

  return (
    <div className="card">
      <h1>Юридические документы</h1>
      {isBlocked ? (
        <p className="muted">Для продолжения работы необходимо принять обязательные документы.</p>
      ) : (
        <p className="muted">Все обязательные документы приняты.</p>
      )}

      {errorMessage ? (
        <div className="card state stack">
          <div>{errorMessage}</div>
          {isAccessBlocked ? (
            <div className="actions">
              <button className="secondary" type="button" onClick={() => void refresh(true)}>
                Обновить
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
      {isLoading ? <div className="muted">Загружаем документы...</div> : null}

      <div className="legal-grid">
        <div className="legal-list">
          {required.map((item) => (
            <div key={`${item.code}-${item.required_version}-${item.locale}`} className="legal-item">
              <div>
                <strong>{item.title}</strong>
                <div className="muted">Код: {item.code}</div>
                <div className="muted">Версия: {item.required_version}</div>
                <div className="muted">Локаль: {item.locale}</div>
                <div className="muted">Вступает: {formatDateTime(item.effective_from, user?.timezone)}</div>
              </div>
              <div className="legal-actions">
                <button
                  className="ghost neft-btn-secondary"
                  type="button"
                  onClick={() => setSelectedCode(item.code)}
                >
                  Прочитать
                </button>
                <label className="checkbox">
                  <input type="checkbox" checked={item.accepted} readOnly />
                  <span>
                    {item.accepted && item.accepted_at
                      ? `Принято ${formatDateTime(item.accepted_at, user?.timezone)}`
                      : "Не принято"}
                  </span>
                </label>
                {!item.accepted ? (
                  <button
                    className="neft-btn-primary"
                    type="button"
                    onClick={() => accept(item.code, item.required_version, item.locale)}
                  >
                    Принять
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
        <div className="legal-preview">
          {selected && document ? (
            <>
              <h2>{document.title}</h2>
              <div className="muted">Версия {document.version}</div>
              <div className="muted">
                Опубликован: {document.published_at ? formatDateTime(document.published_at, user?.timezone) : "—"}
              </div>
              <pre className="legal-content">{document.content}</pre>
            </>
          ) : (
            <div className="muted">Выберите документ, чтобы просмотреть содержание.</div>
          )}
        </div>
      </div>
    </div>
  );
}

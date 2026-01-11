import { useEffect, useMemo, useState } from "react";
import { useLegalGate } from "../auth/LegalGateContext";

const formatDate = (value?: string | null) => {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
};

export function LegalPage() {
  const { required, isBlocked, isLoading, document, loadDocument, accept, refresh } = useLegalGate();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);

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
                <div className="muted">Вступает: {formatDate(item.effective_from)}</div>
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
                  <span>{item.accepted ? `Принято ${formatDate(item.accepted_at)}` : "Не принято"}</span>
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
              <div className="muted">Опубликован: {formatDate(document.published_at)}</div>
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

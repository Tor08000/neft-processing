import { useEffect, useMemo, useState } from "react";
import { useLegalGate } from "../auth/LegalGateContext";
import { EmptyState } from "@shared/ui/EmptyState";
import { useAuth } from "../auth/AuthContext";
import { fetchPartnerLegalProfile } from "../api/partnerLegal";
import type { PartnerLegalProfileResponse } from "../types/partnerLegal";
import { isDemoPartner } from "@shared/demo/demo";

const formatDate = (value?: string | null) => {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
};

const renderScalar = (value: unknown) => {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  return "—";
};

export function LegalPage() {
  const { user } = useAuth();
  const { required, isBlocked, isLoading, document, loadDocument, accept, refresh } = useLegalGate();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [profileState, setProfileState] = useState<PartnerLegalProfileResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const isDemoPartnerAccount = isDemoPartner(user?.email ?? null);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!user) return;
    setProfileLoading(true);
    setProfileError(null);
    fetchPartnerLegalProfile(user.token)
      .then((data) => setProfileState(data))
      .catch((err) => {
        console.error(err);
        setProfileError("Не удалось загрузить юридический профиль");
      })
      .finally(() => setProfileLoading(false));
  }, [user]);

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

  const legalProfile = profileState?.profile ?? null;
  const checklist = profileState?.checklist;
  const statusLabel = legalProfile?.legal_status ?? "Не заполнен";
  const taxContext = legalProfile?.tax_context ?? null;

  return (
    <div className="neft-container">
      <div className="card">
        <h1>Legal & Tax</h1>
      <div className="legal-summary">
        <div>
          <div className="muted">Статус профиля</div>
          <div className="legal-status">{statusLabel}</div>
        </div>
        {profileLoading ? <div className="muted">Проверяем профиль...</div> : null}
        {profileError ? <div className="error">{profileError}</div> : null}
        <div className="actions">
          <button type="button" className="primary" disabled={isDemoPartnerAccount} title={isDemoPartnerAccount ? "Доступно в рабочем контуре" : undefined}>
            Заполнить профиль
          </button>
        </div>
      </div>
      {checklist ? (
        <div className="legal-checklist">
          <div className="legal-checklist__item">
            <span>Юр. профиль</span>
            <span>{checklist.legal_profile ? "✅" : "⛔"}</span>
          </div>
          <div className="legal-checklist__item">
            <span>Реквизиты</span>
            <span>{checklist.legal_details ? "✅" : "⛔"}</span>
          </div>
          <div className="legal-checklist__item">
            <span>Верификация</span>
            <span>{checklist.verified ? "✅" : "⛔"}</span>
          </div>
        </div>
      ) : null}
      {legalProfile ? (
        <div className="legal-tax-card">
          <div className="muted">Налоговый профиль</div>
          <div className="legal-tax-grid">
            <div>
              <strong>Тип</strong>
              <div>{legalProfile.legal_type}</div>
            </div>
            <div>
              <strong>Режим</strong>
              <div>{legalProfile.tax_regime ?? "—"}</div>
            </div>
            <div>
              <strong>НДС</strong>
              <div>{legalProfile.vat_applicable ? `Да (${legalProfile.vat_rate ?? 0}%)` : "Нет"}</div>
            </div>
            <div>
              <strong>Ставка</strong>
              <div>{renderScalar(taxContext?.tax_rate)}</div>
            </div>
          </div>
        </div>
      ) : null}
      {isBlocked ? (
        <p className="muted">Для продолжения работы необходимо принять обязательные документы.</p>
      ) : (
        <p className="muted">Все обязательные документы приняты.</p>
      )}

      {isLoading ? <div className="muted">Загружаем документы...</div> : null}

      <div className="legal-grid">
        <div className="legal-list">
          {required.length === 0 && !isLoading ? (
            <EmptyState
              title="Нет обязательных документов"
              description="Юридические документы ещё не настроены."
              hint="Мы уведомим вас, как только они будут доступны для подписания."
              primaryAction={{ label: "Обновить", onClick: () => void refresh() }}
            />
          ) : (
            required.map((item) => (
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
            ))
          )}
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
    </div>
  );
}

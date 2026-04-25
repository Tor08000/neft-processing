import { useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import {
  activatePartnerOnboarding,
  fetchPartnerOnboarding,
  patchPartnerOnboardingProfile,
  type PartnerOnboardingSnapshot,
} from "../api/partnerOnboarding";
import { fetchPartnerLegalProfile, upsertPartnerLegalDetails, upsertPartnerLegalProfile } from "../api/partnerLegal";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { useLegalGate } from "../auth/LegalGateContext";
import { usePortal } from "../auth/PortalContext";
import { resolvePartnerPortalSurface } from "../access/partnerWorkspace";
import { ErrorState, LoadingState } from "../components/states";
import type { PartnerLegalDetailsUpdate, PartnerLegalProfileUpdate } from "../types/partnerLegal";

const prettyJson = (value: Record<string, unknown> | undefined) => JSON.stringify(value ?? {}, null, 2);

const LEGAL_TYPE_OPTIONS = [
  { value: "LEGAL_ENTITY", label: "Юрлицо" },
  { value: "IP", label: "ИП" },
  { value: "INDIVIDUAL", label: "Физлицо" },
];

const TAX_REGIME_OPTIONS = [
  { value: "", label: "Не выбрано" },
  { value: "USN", label: "УСН" },
  { value: "OSNO", label: "ОСНО" },
  { value: "SELF_EMPLOYED", label: "Самозанятый" },
  { value: "FOREIGN", label: "Иностранный режим" },
  { value: "OTHER", label: "Другое" },
];

const REASON_LABELS: Record<string, string> = {
  profile_incomplete: "Заполните бренд и ключевые контакты.",
  legal_documents_pending: "Примите обязательные legal документы.",
  legal_profile_missing: "Заполните юридический профиль.",
  legal_details_missing: "Заполните реквизиты и банковские данные.",
  legal_details_incomplete: "Доведите реквизиты до полного набора.",
  legal_review_pending: "Ожидается проверка юрпрофиля администратором.",
  legal_review_blocked: "Юрпрофиль заблокирован и требует нового прохода.",
};

const formatReason = (reason: string) => REASON_LABELS[reason] ?? reason;

export function PartnerOnboardingPage() {
  const { user } = useAuth();
  const { portal, refresh: refreshPortal, portalState, isLoading: portalLoading } = usePortal();
  const { required, isBlocked, isLoading: legalLoading, accept, refresh: refreshLegal } = useLegalGate();
  const [snapshot, setSnapshot] = useState<PartnerOnboardingSnapshot | null>(null);
  const [brandName, setBrandName] = useState("");
  const [contactsText, setContactsText] = useState("{}");
  const [profileForm, setProfileForm] = useState<PartnerLegalProfileUpdate>({
    legal_type: "LEGAL_ENTITY",
    country: "RU",
    tax_residency: "RU",
    tax_regime: "USN",
    vat_applicable: false,
    vat_rate: null,
  });
  const [detailsForm, setDetailsForm] = useState<PartnerLegalDetailsUpdate>({
    legal_name: "",
    inn: "",
    kpp: "",
    ogrn: "",
    passport: "",
    bank_account: "",
    bank_bic: "",
    bank_name: "",
  });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [profileSaving, setProfileSaving] = useState(false);
  const [legalSaving, setLegalSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadSnapshot = async () => {
    if (!user) {
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [onboarding, legalProfile] = await Promise.all([
        fetchPartnerOnboarding(user.token),
        fetchPartnerLegalProfile(user.token).catch(() => null),
        refreshLegal(true),
      ]);
      setSnapshot(onboarding);
      setBrandName(onboarding.partner.brand_name ?? "");
      setContactsText(prettyJson((onboarding.partner.contacts as Record<string, unknown> | undefined) ?? {}));
      if (legalProfile?.profile) {
        setProfileForm({
          legal_type: legalProfile.profile.legal_type,
          country: legalProfile.profile.country ?? "RU",
          tax_residency: legalProfile.profile.tax_residency ?? "RU",
          tax_regime: legalProfile.profile.tax_regime ?? "",
          vat_applicable: Boolean(legalProfile.profile.vat_applicable),
          vat_rate: legalProfile.profile.vat_rate ?? null,
        });
        setDetailsForm({
          legal_name: legalProfile.profile.details?.legal_name ?? "",
          inn: legalProfile.profile.details?.inn ?? "",
          kpp: legalProfile.profile.details?.kpp ?? "",
          ogrn: legalProfile.profile.details?.ogrn ?? "",
          passport: legalProfile.profile.details?.passport ?? "",
          bank_account: legalProfile.profile.details?.bank_account ?? "",
          bank_bic: legalProfile.profile.details?.bank_bic ?? "",
          bank_name: legalProfile.profile.details?.bank_name ?? "",
        });
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Не удалось загрузить onboarding.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSnapshot();
  }, [user?.token]);

  const contactsPayload = useMemo(() => {
    try {
      return JSON.parse(contactsText) as Record<string, unknown>;
    } catch {
      return null;
    }
  }, [contactsText]);

  if (!user) {
    return null;
  }

  const surface = resolvePartnerPortalSurface(portal);
  if (
    portalState === "READY" &&
    portal?.access_state === "ACTIVE" &&
    portal?.access_reason !== "partner_onboarding"
  ) {
    return <Navigate to={surface.defaultRoute} replace />;
  }

  if (portalState === "LOADING" || portalLoading || loading) {
    return <LoadingState label="Готовим onboarding партнёра..." />;
  }

  if (loadError || !snapshot) {
    return <ErrorState description={loadError ?? "Onboarding недоступен."} />;
  }

  const saveProfile = async () => {
    if (!contactsPayload) {
      setActionError("Контакты должны быть валидным JSON.");
      return;
    }
    setProfileSaving(true);
    setActionError(null);
    setNotice(null);
    try {
      const updated = await patchPartnerOnboardingProfile(user.token, {
        brand_name: brandName || undefined,
        contacts: contactsPayload,
      });
      setSnapshot((current) => (current ? { ...current, partner: { ...current.partner, ...updated } } : current));
      await Promise.all([loadSnapshot(), refreshPortal()]);
      setNotice("Профиль onboarding обновлён.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось обновить профиль.");
    } finally {
      setProfileSaving(false);
    }
  };

  const saveLegal = async () => {
    setLegalSaving(true);
    setActionError(null);
    setNotice(null);
    try {
      await upsertPartnerLegalProfile(user.token, {
        ...profileForm,
        tax_regime: profileForm.tax_regime || null,
      });
      await upsertPartnerLegalDetails(user.token, detailsForm);
      await loadSnapshot();
      setNotice("Юридический профиль обновлён.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось обновить legal профиль.");
    } finally {
      setLegalSaving(false);
    }
  };

  const activate = async () => {
    setActivating(true);
    setActionError(null);
    setNotice(null);
    try {
      await activatePartnerOnboarding(user.token);
      await Promise.all([refreshPortal(), loadSnapshot()]);
      setNotice("Партнёр активирован.");
    } catch (err) {
      if (err instanceof ApiError && err.details && typeof err.details === "object") {
        const blocked = (err.details as { blocked_reasons?: string[] }).blocked_reasons ?? [];
        setActionError(blocked.length ? blocked.map(formatReason).join(" ") : err.message);
      } else {
        setActionError(err instanceof Error ? err.message : "Не удалось активировать партнёра.");
      }
    } finally {
      setActivating(false);
    }
  };

  const acceptDocument = async (code: string, version: string, locale: string) => {
    setActionError(null);
    setNotice(null);
    try {
      await accept(code, version, locale);
      await Promise.all([refreshLegal(true), loadSnapshot()]);
      setNotice("Legal документ принят.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось принять документ.");
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Onboarding партнёра</h2>
            <p className="muted">
              Завершите профиль, legal шаги и активацию, чтобы открыть полноценный кабинет без временных ограничений.
            </p>
          </div>
          <div className="actions">
            <Link className="ghost" to="/support/requests">
              Поддержка
            </Link>
            <Link className="ghost" to="/legal">
              Legal
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Партнёр</div>
            <div>{snapshot.partner.legal_name}</div>
          </div>
          <div>
            <div className="label">Код</div>
            <div className="mono">{snapshot.partner.code}</div>
          </div>
          <div>
            <div className="label">Статус</div>
            <div>{snapshot.partner.status}</div>
          </div>
          <div>
            <div className="label">Следующий шаг</div>
            <div>{snapshot.checklist.next_step}</div>
          </div>
        </div>
        <div className="card__section">
          <div className="label">Чек-лист</div>
          <div className="meta-grid">
            <div>Профиль: {snapshot.checklist.profile_complete ? "готов" : "нужно заполнить"}</div>
            <div>Legal документы: {snapshot.checklist.legal_documents_accepted ? "приняты" : "ожидаются"}</div>
            <div>Юрпрофиль: {snapshot.checklist.legal_profile_present ? "заполнен" : "не заполнен"}</div>
            <div>Реквизиты: {snapshot.checklist.legal_details_complete ? "полные" : "неполные"}</div>
            <div>Верификация: {snapshot.checklist.legal_verified ? "VERIFIED" : "ожидается"}</div>
            <div>Активация: {snapshot.checklist.activation_ready ? "готова" : "заблокирована"}</div>
          </div>
          {snapshot.checklist.blocked_reasons.length ? (
            <ul className="card__list">
              {snapshot.checklist.blocked_reasons.map((reason) => (
                <li key={reason}>{formatReason(reason)}</li>
              ))}
            </ul>
          ) : (
            <div className="notice success">Все внутренние шаги закрыты, можно активировать партнёра.</div>
          )}
          {notice ? <div className="notice success">{notice}</div> : null}
          {actionError ? <div className="notice error">{actionError}</div> : null}
        </div>
      </section>

      <section className="card">
        <h2>Шаг 1. Профиль</h2>
        <p className="muted">Этот шаг позволяет pending-партнёрам заполнить профиль до полной активации.</p>
        <div className="card__section">
          <label className="filter">
            Бренд
            <input value={brandName} onChange={(event) => setBrandName(event.target.value)} disabled={profileSaving} />
          </label>
        </div>
        <div className="card__section">
          <label className="filter">
            Контакты (JSON)
            <textarea rows={8} value={contactsText} onChange={(event) => setContactsText(event.target.value)} disabled={profileSaving} />
          </label>
          {!contactsPayload ? <div className="notice error">Контакты должны быть валидным JSON.</div> : null}
          <div className="actions">
            <button type="button" className="primary" onClick={() => void saveProfile()} disabled={profileSaving || !contactsPayload}>
              {profileSaving ? "Сохраняем..." : "Сохранить профиль"}
            </button>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>Шаг 2. Юридический профиль и реквизиты</h2>
        <p className="muted">Финальная проверка остаётся за оператором, но партнёр может подготовить legal пакет самостоятельно.</p>
        <div className="meta-grid">
          <label className="filter">
            Тип
            <select value={profileForm.legal_type} onChange={(event) => setProfileForm((prev) => ({ ...prev, legal_type: event.target.value }))} disabled={legalSaving}>
              {LEGAL_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Страна
            <input value={profileForm.country ?? ""} onChange={(event) => setProfileForm((prev) => ({ ...prev, country: event.target.value }))} disabled={legalSaving} />
          </label>
          <label className="filter">
            Налоговое резидентство
            <input
              value={profileForm.tax_residency ?? ""}
              onChange={(event) => setProfileForm((prev) => ({ ...prev, tax_residency: event.target.value }))}
              disabled={legalSaving}
            />
          </label>
          <label className="filter">
            Режим
            <select value={profileForm.tax_regime ?? ""} onChange={(event) => setProfileForm((prev) => ({ ...prev, tax_regime: event.target.value }))} disabled={legalSaving}>
              {TAX_REGIME_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={Boolean(profileForm.vat_applicable)}
              onChange={(event) => setProfileForm((prev) => ({ ...prev, vat_applicable: event.target.checked }))}
              disabled={legalSaving}
            />
            <span>НДС применим</span>
          </label>
          <label className="filter">
            Ставка НДС
            <input
              type="number"
              value={profileForm.vat_rate ?? ""}
              onChange={(event) =>
                setProfileForm((prev) => ({
                  ...prev,
                  vat_rate: event.target.value === "" ? null : Number(event.target.value),
                }))
              }
              disabled={legalSaving}
            />
          </label>
        </div>
        <div className="meta-grid">
          <label className="filter">
            Юр. наименование
            <input value={detailsForm.legal_name ?? ""} onChange={(event) => setDetailsForm((prev) => ({ ...prev, legal_name: event.target.value }))} disabled={legalSaving} />
          </label>
          <label className="filter">
            ИНН
            <input value={detailsForm.inn ?? ""} onChange={(event) => setDetailsForm((prev) => ({ ...prev, inn: event.target.value }))} disabled={legalSaving} />
          </label>
          <label className="filter">
            КПП
            <input value={detailsForm.kpp ?? ""} onChange={(event) => setDetailsForm((prev) => ({ ...prev, kpp: event.target.value }))} disabled={legalSaving} />
          </label>
          <label className="filter">
            ОГРН
            <input value={detailsForm.ogrn ?? ""} onChange={(event) => setDetailsForm((prev) => ({ ...prev, ogrn: event.target.value }))} disabled={legalSaving} />
          </label>
          <label className="filter">
            Паспорт
            <input value={detailsForm.passport ?? ""} onChange={(event) => setDetailsForm((prev) => ({ ...prev, passport: event.target.value }))} disabled={legalSaving} />
          </label>
          <label className="filter">
            Расчётный счёт
            <input
              value={detailsForm.bank_account ?? ""}
              onChange={(event) => setDetailsForm((prev) => ({ ...prev, bank_account: event.target.value }))}
              disabled={legalSaving}
            />
          </label>
          <label className="filter">
            БИК
            <input value={detailsForm.bank_bic ?? ""} onChange={(event) => setDetailsForm((prev) => ({ ...prev, bank_bic: event.target.value }))} disabled={legalSaving} />
          </label>
          <label className="filter">
            Банк
            <input value={detailsForm.bank_name ?? ""} onChange={(event) => setDetailsForm((prev) => ({ ...prev, bank_name: event.target.value }))} disabled={legalSaving} />
          </label>
        </div>
        <div className="actions">
          <button type="button" className="primary" onClick={() => void saveLegal()} disabled={legalSaving}>
            {legalSaving ? "Сохраняем..." : "Сохранить legal данные"}
          </button>
          <Link className="ghost" to="/legal">
            Открыть legal раздел
          </Link>
        </div>
      </section>

      <section className="card">
        <h2>Шаг 3. Обязательные документы</h2>
        {legalLoading ? <div className="muted">Проверяем обязательные документы...</div> : null}
        {!required.length && !legalLoading ? (
          <div className="notice">Для текущего контура нет обязательных документов или legal gate отключён.</div>
        ) : null}
        {required.map((item) => (
          <div key={`${item.code}-${item.required_version}-${item.locale}`} className="card__section">
            <div>
              <strong>{item.title}</strong>
              <div className="muted">
                {item.code} · {item.required_version} · {item.locale}
              </div>
            </div>
            <div className="actions">
              {item.accepted ? <span className="notice success">Принято</span> : null}
              {!item.accepted ? (
                <button type="button" className="primary" onClick={() => void acceptDocument(item.code, item.required_version, item.locale)}>
                  Принять
                </button>
              ) : null}
            </div>
          </div>
        ))}
        {isBlocked ? <div className="notice">Пока не приняты обязательные документы, часть действий остаётся ограниченной.</div> : null}
      </section>

      <section className="card">
        <h2>Шаг 4. Активация</h2>
        <p className="muted">Кнопка станет рабочей только когда профиль, legal шаги и admin verification реально готовы.</p>
        <div className="actions">
          <button type="button" className="primary" onClick={() => void activate()} disabled={activating || !snapshot.checklist.activation_ready}>
            {activating ? "Активируем..." : "Активировать партнёра"}
          </button>
          <Link className="ghost" to="/support/requests">
            Нужна помощь
          </Link>
        </div>
      </section>
    </div>
  );
}

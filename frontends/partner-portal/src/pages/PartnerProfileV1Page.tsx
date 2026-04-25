import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerMeV1, patchPartnerMeV1, type PartnerMeV1Response } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { canManagePartnerProfile } from "../access/partnerWorkspace";
import { LoadingState, ErrorState } from "../components/states";
import { PartnerSupportActions } from "../components/PartnerSupportActions";

const prettyJson = (value: Record<string, unknown> | undefined) => JSON.stringify(value ?? {}, null, 2);

const renderScalar = (value: unknown) => {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  return "—";
};

export function PartnerProfileV1Page() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const canManage = canManagePartnerProfile(portal, user?.roles);
  const [profile, setProfile] = useState<PartnerMeV1Response["partner"] | null>(null);
  const [contactsText, setContactsText] = useState("{}");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setLoadError(null);
    fetchPartnerMeV1(user.token)
      .then((response) => {
        setProfile(response.partner);
        setContactsText(prettyJson(response.partner.contacts));
      })
      .catch((err: Error) => setLoadError(err.message))
      .finally(() => setLoading(false));
  }, [user]);

  const parsedContacts = useMemo(() => {
    try {
      return JSON.parse(contactsText) as Record<string, unknown>;
    } catch {
      return null;
    }
  }, [contactsText]);

  const contactEntries = useMemo(
    () => Object.entries(parsedContacts ?? profile?.contacts ?? {}).slice(0, 6),
    [parsedContacts, profile?.contacts],
  );

  if (!user) return null;
  if (loading) return <LoadingState label="Загружаем профиль партнёра..." />;
  if (loadError) return <ErrorState description={loadError} />;
  if (!profile) return <ErrorState description="Профиль партнёра недоступен." />;

  const handleSave = async () => {
    if (!parsedContacts || !user) {
      setSaveError("Контакты должны быть валидным JSON.");
      return;
    }
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);
    try {
      const updated = await patchPartnerMeV1(user.token, {
        brand_name: profile.brand_name ?? undefined,
        contacts: parsedContacts,
      });
      setProfile((prev) => ({
        ...(prev ?? profile),
        brand_name: updated.brand_name ?? null,
        contacts: updated.contacts ?? parsedContacts,
      }));
      setContactsText(prettyJson((updated.contacts as Record<string, unknown> | undefined) ?? parsedContacts));
      setSaveSuccess("Профиль обновлён.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Не удалось обновить профиль.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Профиль партнёра</h2>
            <p className="muted">Реквизиты и контактные данные, которые используются в partner shell и связанных legal/support workflows.</p>
          </div>
          <div className="actions">
            <Link className="ghost" to="/partner/terms">
              Условия
            </Link>
            <Link className="ghost" to="/legal">
              Legal
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Код партнёра</div>
            <div className="mono">{profile.code}</div>
          </div>
          <div>
            <div className="label">Тип</div>
            <div>{renderScalar(profile.partner_type)}</div>
          </div>
          <div>
            <div className="label">Статус</div>
            <div>{renderScalar(profile.status)}</div>
          </div>
          <div>
            <div className="label">ИНН / ОГРН</div>
            <div>{[renderScalar(profile.inn), renderScalar(profile.ogrn)].join(" / ")}</div>
          </div>
        </div>
        <div className="card__section">
          <div className="label">Юридическое лицо</div>
          <div>{profile.legal_name}</div>
        </div>
        <div className="card__section">
          <label className="filter">
            Бренд
            <input
              value={profile.brand_name ?? ""}
              onChange={(event) => {
                setProfile((prev) => (prev ? { ...prev, brand_name: event.target.value } : prev));
                setSaveSuccess(null);
              }}
              disabled={!canManage || saving}
            />
          </label>
        </div>
        <div className="card__section">
          <div className="label">Ключевые контакты</div>
          {contactEntries.length ? (
            <div className="meta-grid">
              {contactEntries.map(([key, value]) => (
                <div key={key}>
                  <div className="label">{key}</div>
                  <div>{renderScalar(value)}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">Контакты пока не заполнены.</p>
          )}
        </div>
        <div className="card__section">
          <label className="filter">
            Контакты (JSON)
            <textarea
              rows={10}
              value={contactsText}
              onChange={(event) => {
                setContactsText(event.target.value);
                setSaveSuccess(null);
              }}
              disabled={!canManage || saving}
            />
          </label>
          {!parsedContacts ? <div className="notice error">Контакты должны быть валидным JSON.</div> : null}
          {!canManage ? <div className="notice">Режим только для чтения. Изменять профиль могут owner, manager и finance manager.</div> : null}
          {saveError ? <div className="notice error">{saveError}</div> : null}
          {saveSuccess ? <div className="notice success">{saveSuccess}</div> : null}
          {canManage ? (
            <div className="actions">
              <button type="button" className="primary" onClick={() => void handleSave()} disabled={saving || !parsedContacts}>
                {saving ? "Сохраняем..." : "Сохранить профиль"}
              </button>
            </div>
          ) : null}
        </div>
      </section>

      <PartnerSupportActions
        title="Нужна помощь по реквизитам или профилю?"
        description="Создайте partner support case, если данные не сходятся с договором, legal gate или onboarding truth."
        requestTitle="Нужна помощь по профилю партнёра"
        relatedLinks={[
          { to: "/support/requests", label: "История обращений" },
          { to: "/partner/users", label: "Пользователи" },
        ]}
      />
    </div>
  );
}

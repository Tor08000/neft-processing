import { useEffect, useMemo, useState } from "react";
import {
  disableHelpdeskIntegration,
  enableHelpdeskIntegration,
  fetchHelpdeskIntegration,
  updateHelpdeskIntegration,
} from "../api/helpdesk";
import { updateClientTimezone } from "../api/clientPortal";
import { useAuth } from "../auth/AuthContext";
import { AppForbiddenState } from "../components/states";
import type { HelpdeskIntegration, HelpdeskProvider } from "../types/helpdesk";
import { hasAnyRole } from "../utils/roles";

const POPULAR_TIMEZONES = [
  "Europe/Moscow",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Istanbul",
  "Europe/Minsk",
  "Asia/Dubai",
  "Asia/Almaty",
  "Asia/Tbilisi",
  "Asia/Yerevan",
  "Asia/Novosibirsk",
  "Asia/Vladivostok",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Singapore",
  "Asia/Seoul",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Sao_Paulo",
  "Australia/Sydney",
  "UTC",
];

export function SettingsPage() {
  const { user, setTimezone } = useAuth();
  const [timezoneValue, setTimezoneValue] = useState(user?.timezone ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const isHelpdeskAdmin = useMemo(
    () => Boolean(user && hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"])),
    [user],
  );
  const [helpdeskIntegration, setHelpdeskIntegration] = useState<HelpdeskIntegration | null>(null);
  const [helpdeskLoading, setHelpdeskLoading] = useState(false);
  const [helpdeskSaving, setHelpdeskSaving] = useState(false);
  const [helpdeskError, setHelpdeskError] = useState("");
  const [helpdeskSuccess, setHelpdeskSuccess] = useState(false);
  const [helpdeskProvider, setHelpdeskProvider] = useState<HelpdeskProvider>("zendesk");
  const [helpdeskBaseUrl, setHelpdeskBaseUrl] = useState("");
  const [helpdeskApiEmail, setHelpdeskApiEmail] = useState("");
  const [helpdeskApiToken, setHelpdeskApiToken] = useState("");
  const [helpdeskBrandId, setHelpdeskBrandId] = useState("");

  const availableTimezones = useMemo(() => {
    const supportedValuesOf = (Intl as typeof Intl & { supportedValuesOf?: (type: string) => string[] })
      .supportedValuesOf;
    if (typeof supportedValuesOf === "function") {
      return supportedValuesOf("timeZone");
    }
    return POPULAR_TIMEZONES;
  }, []);

  useEffect(() => {
    if (!user || !isHelpdeskAdmin) return;
    setHelpdeskLoading(true);
    setHelpdeskError("");
    fetchHelpdeskIntegration(user)
      .then((response) => {
        const integration = response.integration ?? null;
        setHelpdeskIntegration(integration);
        if (integration) {
          setHelpdeskProvider(integration.provider);
          setHelpdeskBaseUrl(integration.base_url ?? "");
          setHelpdeskBrandId(integration.brand_id ?? "");
        }
      })
      .catch((err) => {
        console.error("Не удалось загрузить helpdesk интеграцию", err);
        setHelpdeskError("Не удалось загрузить helpdesk интеграцию");
      })
      .finally(() => setHelpdeskLoading(false));
  }, [user, isHelpdeskAdmin]);

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация." />;
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Settings</h2>
          <p className="muted">Read-only параметры доступа и профиля клиента.</p>
        </div>
      </div>
      <dl className="meta-grid">
        <div>
          <dt className="label">Email</dt>
          <dd>{user.email}</dd>
        </div>
        <div>
          <dt className="label">Client ID</dt>
          <dd>{user.clientId ?? "—"}</dd>
        </div>
        <div>
          <dt className="label">Roles</dt>
          <dd>{user.roles.join(", ")}</dd>
        </div>
        <div>
          <dt className="label">Subject type</dt>
          <dd>{user.subjectType}</dd>
        </div>
        <div>
          <dt className="label">Timezone</dt>
          <dd>{user.timezone ?? "—"}</dd>
        </div>
      </dl>
      <div className="card__section">
        <div className="stack">
          <div>
            <h3>Таймзона</h3>
            <p className="muted">Эта таймзона влияет на отображение времени и уведомления.</p>
          </div>
          <div className="stack-inline">
            <div className="stack">
              <label htmlFor="timezone-input" className="label">
                Выберите таймзону
              </label>
              <input
                id="timezone-input"
                list="timezone-options"
                value={timezoneValue}
                onChange={(event) => {
                  setTimezoneValue(event.target.value);
                  setError("");
                  setSuccess(false);
                }}
                placeholder="Начните ввод (например, Europe/Moscow)"
              />
              <datalist id="timezone-options">
                {availableTimezones.map((tz) => (
                  <option key={tz} value={tz} />
                ))}
              </datalist>
            </div>
            <button
              type="button"
              className="neft-btn neft-btn-primary"
              disabled={isSaving || !timezoneValue}
              onClick={async () => {
                if (!timezoneValue) return;
                setIsSaving(true);
                setError("");
                setSuccess(false);
                try {
                  const response = await updateClientTimezone(user, timezoneValue);
                  setTimezone(response.timezone ?? timezoneValue);
                  setSuccess(true);
                } catch (err) {
                  console.error("Не удалось сохранить таймзону", err);
                  setError("Не удалось сохранить таймзону");
                } finally {
                  setIsSaving(false);
                }
              }}
            >
              {isSaving ? "Сохраняем…" : "Сохранить"}
            </button>
          </div>
          {error ? <div className="muted">{error}</div> : null}
          {success ? <div className="muted">Таймзона обновлена.</div> : null}
          {!timezoneValue ? (
            <div className="muted small">
              Популярные варианты: {POPULAR_TIMEZONES.slice(0, 6).join(", ")}
            </div>
          ) : null}
        </div>
      </div>
      {isHelpdeskAdmin ? (
        <div className="card__section">
          <div className="stack">
            <div>
              <h3>Helpdesk интеграция</h3>
              <p className="muted">Настройте подключение к Zendesk для синхронизации тикетов.</p>
            </div>
            <dl className="meta-grid">
              <div>
                <dt className="label">Статус</dt>
                <dd>{helpdeskIntegration?.status === "ACTIVE" ? "ON" : "OFF"}</dd>
              </div>
              <div>
                <dt className="label">Провайдер</dt>
                <dd>{helpdeskIntegration?.provider ?? "zendesk"}</dd>
              </div>
              <div>
                <dt className="label">Base URL</dt>
                <dd>{helpdeskIntegration?.base_url ?? "—"}</dd>
              </div>
              <div>
                <dt className="label">Последняя ошибка</dt>
                <dd>{helpdeskIntegration?.last_error ?? "—"}</dd>
              </div>
            </dl>
            <div className="stack-inline">
              <div className="stack">
                <label className="label" htmlFor="helpdesk-provider">
                  Провайдер
                </label>
                <select
                  id="helpdesk-provider"
                  value={helpdeskProvider}
                  onChange={(event) => setHelpdeskProvider(event.target.value as HelpdeskProvider)}
                >
                  <option value="zendesk">Zendesk</option>
                </select>
              </div>
              <div className="stack">
                <label className="label" htmlFor="helpdesk-base-url">
                  Base URL
                </label>
                <input
                  id="helpdesk-base-url"
                  placeholder="https://your-domain.zendesk.com"
                  value={helpdeskBaseUrl}
                  onChange={(event) => setHelpdeskBaseUrl(event.target.value)}
                />
              </div>
              <div className="stack">
                <label className="label" htmlFor="helpdesk-api-email">
                  API email
                </label>
                <input
                  id="helpdesk-api-email"
                  placeholder="support@company.com"
                  value={helpdeskApiEmail}
                  onChange={(event) => setHelpdeskApiEmail(event.target.value)}
                />
              </div>
              <div className="stack">
                <label className="label" htmlFor="helpdesk-api-token">
                  API token
                </label>
                <input
                  id="helpdesk-api-token"
                  type="password"
                  placeholder="••••••••"
                  value={helpdeskApiToken}
                  onChange={(event) => setHelpdeskApiToken(event.target.value)}
                />
              </div>
              <div className="stack">
                <label className="label" htmlFor="helpdesk-brand-id">
                  Brand ID
                </label>
                <input
                  id="helpdesk-brand-id"
                  placeholder="optional"
                  value={helpdeskBrandId}
                  onChange={(event) => setHelpdeskBrandId(event.target.value)}
                />
              </div>
            </div>
            <div className="stack-inline">
              <button
                type="button"
                className="neft-btn neft-btn-primary"
                disabled={helpdeskSaving || helpdeskLoading || !helpdeskBaseUrl}
                onClick={async () => {
                  if (!user || !helpdeskBaseUrl) return;
                  setHelpdeskSaving(true);
                  setHelpdeskError("");
                  setHelpdeskSuccess(false);
                  try {
                    const config = {
                      base_url: helpdeskBaseUrl.trim(),
                      ...(helpdeskApiEmail ? { api_email: helpdeskApiEmail } : {}),
                      ...(helpdeskApiToken ? { api_token: helpdeskApiToken } : {}),
                      ...(helpdeskBrandId ? { brand_id: helpdeskBrandId } : {}),
                    };
                    const payload = { provider: helpdeskProvider, config };
                    const shouldEnable =
                      !helpdeskIntegration || helpdeskIntegration.status === "DISABLED";
                    const response = shouldEnable
                      ? await enableHelpdeskIntegration(payload, user)
                      : await updateHelpdeskIntegration(payload, user);
                    setHelpdeskIntegration(response.integration ?? null);
                    setHelpdeskApiToken("");
                    setHelpdeskSuccess(true);
                  } catch (err) {
                    console.error("Не удалось сохранить helpdesk интеграцию", err);
                    setHelpdeskError("Не удалось сохранить helpdesk интеграцию");
                  } finally {
                    setHelpdeskSaving(false);
                  }
                }}
              >
                {helpdeskSaving
                  ? "Сохраняем…"
                  : helpdeskIntegration?.status === "DISABLED" || !helpdeskIntegration
                    ? "Включить"
                    : "Обновить"}
              </button>
              {helpdeskIntegration?.status === "ACTIVE" ? (
                <button
                  type="button"
                  className="neft-btn"
                  disabled={helpdeskSaving}
                  onClick={async () => {
                    if (!user) return;
                    setHelpdeskSaving(true);
                    setHelpdeskError("");
                    setHelpdeskSuccess(false);
                    try {
                      const response = await disableHelpdeskIntegration(user);
                      setHelpdeskIntegration(response.integration ?? null);
                      setHelpdeskSuccess(true);
                    } catch (err) {
                      console.error("Не удалось отключить helpdesk", err);
                      setHelpdeskError("Не удалось отключить helpdesk");
                    } finally {
                      setHelpdeskSaving(false);
                    }
                  }}
                >
                  Отключить
                </button>
              ) : null}
            </div>
            {helpdeskLoading ? <div className="muted">Загружаем интеграцию…</div> : null}
            {helpdeskError ? <div className="muted">{helpdeskError}</div> : null}
            {helpdeskSuccess ? <div className="muted">Настройки helpdesk обновлены.</div> : null}
          </div>
        </div>
      ) : (
        <div className="card__section">
          <div className="muted">Helpdesk интеграция доступна только для OWNER/ADMIN.</div>
        </div>
      )}
    </div>
  );
}

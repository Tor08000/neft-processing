import { useMemo, useState } from "react";
import { updateClientTimezone } from "../api/clientPortal";
import { useAuth } from "../auth/AuthContext";
import { AppForbiddenState } from "../components/states";

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

  const availableTimezones = useMemo(() => {
    const supportedValuesOf = (Intl as typeof Intl & { supportedValuesOf?: (type: string) => string[] })
      .supportedValuesOf;
    if (typeof supportedValuesOf === "function") {
      return supportedValuesOf("timeZone");
    }
    return POPULAR_TIMEZONES;
  }, []);

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
    </div>
  );
}

import { useEffect, useState } from "react";
import { fetchSettings, type PartnerSettings } from "../api/partner";
import { useAuth } from "../auth/AuthContext";

export function SettingsPage() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<PartnerSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    fetchSettings(user.token)
      .then((data) => {
        if (active) {
          setSettings(data);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить настройки партнёра");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [user]);

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Настройки</h2>
          <span className="muted">read-only v1</span>
        </div>
        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <div className="error" role="alert">
            {error}
          </div>
        ) : settings ? (
          <div className="stack">
            <div className="card__section">
              <h3>Профиль</h3>
              <div className="meta-grid">
                <div>
                  <div className="label">Партнёр</div>
                  <div>{settings.profile.name}</div>
                </div>
                <div>
                  <div className="label">Юр. лицо</div>
                  <div>{settings.profile.legalName ?? "—"}</div>
                </div>
                <div>
                  <div className="label">ИНН</div>
                  <div>{settings.profile.inn ?? "—"}</div>
                </div>
                <div>
                  <div className="label">Расчётный счёт</div>
                  <div>{settings.profile.settlementAccount ?? "—"}</div>
                </div>
                <div>
                  <div className="label">Email</div>
                  <div>{settings.profile.contactEmail ?? user?.email ?? "—"}</div>
                </div>
              </div>
            </div>

            <div className="card__section">
              <h3>Интеграции</h3>
              {settings.integrations.length ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Параметр</th>
                      <th>Значение</th>
                    </tr>
                  </thead>
                  <tbody>
                    {settings.integrations.map((item) => (
                      <tr key={item.name}>
                        <td>{item.name}</td>
                        <td>{item.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">Интеграции не настроены.</p>
              )}
            </div>

            <div className="card__section">
              <h3>Пользователи</h3>
              {settings.users.length ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Роль</th>
                    </tr>
                  </thead>
                  <tbody>
                    {settings.users.map((userItem) => (
                      <tr key={userItem.id}>
                        <td>{userItem.email}</td>
                        <td>{userItem.role}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">Пользователи не добавлены.</p>
              )}
            </div>
          </div>
        ) : (
          <p className="muted">Настройки не доступны.</p>
        )}
      </section>
    </div>
  );
}

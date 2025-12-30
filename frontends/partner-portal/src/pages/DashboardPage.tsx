import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { fetchPartnerProfile, type PartnerProfile } from "../api/partner";

function formatExpiry(timestamp: number | undefined) {
  if (!timestamp) return "—";
  const diffMs = timestamp - Date.now();
  if (diffMs <= 0) return "истек";
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "менее минуты";
  if (minutes < 60) return `${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  return `${hours} ч ${restMinutes} мин`;
}

export function DashboardPage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<PartnerProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    if (!user) return;
    setIsLoading(true);
    fetchPartnerProfile(user.token)
      .then((data) => {
        if (isMounted) {
          setProfile(data);
        }
      })
      .catch((err) => {
        console.error(err);
        if (isMounted) {
          setError("Не удалось загрузить профиль партнёра");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [user]);

  const abilities = useMemo(() => {
    if (!user) return [] as string[];
    const list: string[] = [];
    if (user.roles.includes("PARTNER_OWNER")) {
      list.push("Полный доступ к кабинету партнёра");
    }
    if (user.roles.includes("PARTNER_ACCOUNTANT")) {
      list.push("Доступ к выплатам и документам");
    }
    if (user.roles.includes("PARTNER_OPERATOR")) {
      list.push("Доступ к АЗС и операциям");
    }
    if (user.roles.includes("PARTNER_SERVICE_MANAGER")) {
      list.push("Доступ к каталогу сервисов");
    }
    return list;
  }, [user]);

  if (!user) {
    return null;
  }

  return (
    <div className="stack" aria-live="polite">
      <section className="card">
        <h2>Здравствуйте, {user.email}</h2>
        <p className="muted">Добро пожаловать в кабинет партнёра NEFT.</p>
      </section>

      <section className="card">
        <h3>Профиль партнёра</h3>
        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <div className="error" role="alert">
            {error}
          </div>
        ) : profile ? (
          <div className="meta-grid">
            <div>
              <div className="label">Партнёр</div>
              <div>{profile.name}</div>
            </div>
            <div>
              <div className="label">Юр. лицо</div>
              <div>{profile.legalName ?? "—"}</div>
            </div>
            <div>
              <div className="label">ИНН</div>
              <div>{profile.inn ?? "—"}</div>
            </div>
            <div>
              <div className="label">Email</div>
              <div>{profile.contactEmail ?? user.email}</div>
            </div>
          </div>
        ) : (
          <p className="muted">Профиль не заполнен.</p>
        )}
      </section>

      <section className="card">
        <h3>Ваши роли</h3>
        <ul className="pill-list">
          {user.roles.map((role) => (
            <li key={role}>{role}</li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>Ваши текущие возможности</h3>
        {abilities.length ? (
          <ul className="bullets">
            {abilities.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">Роли не назначены.</p>
        )}
      </section>

      <section className="card">
        <h3>Статус авторизации</h3>
        <div className="meta-grid">
          <div>
            <div className="label">Email</div>
            <div>{user.email}</div>
          </div>
          <div>
            <div className="label">Тип субъекта</div>
            <div>{user.subjectType}</div>
          </div>
          <div>
            <div className="label">ID партнёра</div>
            <div>{user.partnerId ?? "—"}</div>
          </div>
          <div>
            <div className="label">Токен истекает через</div>
            <div>{formatExpiry(user.expiresAt)}</div>
          </div>
        </div>
      </section>
    </div>
  );
}

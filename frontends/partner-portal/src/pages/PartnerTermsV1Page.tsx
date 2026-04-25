import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerTermsV1, type PartnerTermsV1 } from "../api/partner";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorState, LoadingState } from "../components/states";
import { PartnerSupportActions } from "../components/PartnerSupportActions";

const formatDateTime = (value?: string | null) => {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
};

const renderScalar = (value: unknown) => {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  return "—";
};

export function PartnerTermsV1Page() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const [terms, setTerms] = useState<PartnerTermsV1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEmpty, setIsEmpty] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError(null);
    setIsEmpty(false);
    fetchPartnerTermsV1(user.token)
      .then((response) => setTerms(response))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setIsEmpty(true);
          setTerms(null);
          return;
        }
        setError(err instanceof Error ? err.message : "Не удалось загрузить условия.");
      })
      .finally(() => setLoading(false));
  }, [user]);

  const termEntries = useMemo(
    () => Object.entries(terms?.terms ?? {}).slice(0, 8),
    [terms?.terms],
  );

  if (!user) return null;
  if (loading) return <LoadingState label="Загружаем условия партнёра..." />;
  if (error) return <ErrorState description={error} />;

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Условия</h2>
            <p className="muted">Последняя версия действующих условий и связанный legal state партнёра.</p>
          </div>
          <div className="actions">
            <Link className="ghost" to="/partner/profile">
              Профиль
            </Link>
            <Link className="ghost" to="/legal">
              Legal
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Legal статус</div>
            <div>{portal?.partner?.legal_state?.status ?? "—"}</div>
          </div>
          <div>
            <div className="label">Блокировка</div>
            <div>{portal?.partner?.legal_state?.block_reason ?? "—"}</div>
          </div>
        </div>
        {isEmpty ? (
          <EmptyState
            title="Активных условий нет"
            description="Для этого партнёра ещё не опубликована версия условий или owner не наполнил профиль."
            primaryAction={{ label: "Открыть профиль", to: "/partner/profile" }}
            secondaryAction={{ label: "Открыть legal", to: "/legal" }}
          />
        ) : terms ? (
          <>
            <div className="meta-grid">
              <div>
                <div className="label">Версия</div>
                <div>{terms.version}</div>
              </div>
              <div>
                <div className="label">Статус</div>
                <div>{terms.status}</div>
              </div>
              <div>
                <div className="label">Создано</div>
                <div>{formatDateTime(terms.created_at)}</div>
              </div>
              <div>
                <div className="label">Обновлено</div>
                <div>{formatDateTime(terms.updated_at)}</div>
              </div>
            </div>
            <div className="card__section">
              <h3>Ключевые параметры</h3>
              {termEntries.length ? (
                <div className="meta-grid">
                  {termEntries.map(([key, value]) => (
                    <div key={key}>
                      <div className="label">{key}</div>
                      <div>{renderScalar(value)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">Структурированные параметры условий не заполнены.</p>
              )}
            </div>
            <div className="card__section">
              <details>
                <summary>Сырой payload условий</summary>
                <pre>{JSON.stringify(terms.terms ?? {}, null, 2)}</pre>
              </details>
            </div>
          </>
        ) : null}
      </section>

      <PartnerSupportActions
        title="Нужна помощь по условиям или legal status?"
        description="Создайте support case, если условия не опубликованы, отличаются от договора или legal gate блокирует рабочий кабинет."
        requestTitle="Нужна помощь по условиям партнёра"
        relatedLinks={[
          { to: "/support/requests", label: "История обращений" },
          { to: "/legal", label: "Legal" },
        ]}
      />
    </div>
  );
}

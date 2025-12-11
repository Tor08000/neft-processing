import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { blockCard, fetchCard, unblockCard, updateCardLimit } from "../api/cards";
import type { CardLimit, ClientCard } from "../types/cards";

const DEFAULT_LIMITS: CardLimit[] = [
  { type: "DAILY_AMOUNT", value: 0, window: "DAY" },
  { type: "MONTHLY_AMOUNT", value: 0, window: "MONTH" },
];

export function ClientCardDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [card, setCard] = useState<ClientCard | null>(null);
  const [limitDraft, setLimitDraft] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    fetchCard(id, user)
      .then((data) => {
        setCard(data);
        const initial: Record<string, number> = {};
        data.limits.forEach((limit) => {
          initial[limit.type] = limit.value;
        });
        setLimitDraft(initial);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, user]);

  const limitList = useMemo(() => {
    if (!card) return DEFAULT_LIMITS;
    const known = new Map(card.limits.map((l) => [l.type, l] as const));
    return DEFAULT_LIMITS.map((preset) => known.get(preset.type) ?? preset);
  }, [card]);

  const toggleStatus = async () => {
    if (!card) return;
    const confirmed =
      typeof window === "undefined"
        ? true
        : window.confirm(card.status === "ACTIVE" ? "Заблокировать карту?" : "Разблокировать карту?");
    if (!confirmed) return;
    const fn = card.status === "ACTIVE" ? blockCard : unblockCard;
    try {
      const response = await fn(card.id, user);
      setCard({ ...card, status: response.status });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка обновления статуса");
    }
  };

  const submitLimits = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!card) return;
    try {
      const updates: CardLimit[] = limitList.map((limit) => ({
        ...limit,
        value: Number(limitDraft[limit.type] ?? limit.value),
      }));
      let latest: ClientCard = card;
      for (const update of updates) {
        latest = await updateCardLimit(card.id, update, user);
      }
      setCard(latest);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось обновить лимиты");
    }
  };

  if (loading) {
    return <div className="card">Загрузка данных карты...</div>;
  }

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
  }

  if (!card) {
    return (
      <div className="card error" role="alert">
        Карта не найдена
        <button className="ghost" onClick={() => navigate(-1)} type="button">
          Назад
        </button>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Карта {card.pan_masked ?? card.id}</h2>
            <p className="muted">Статус и базовая информация</p>
          </div>
          <button className="secondary" type="button" onClick={() => void toggleStatus()}>
            {card.status === "ACTIVE" ? "Заблокировать" : "Разблокировать"}
          </button>
        </div>

        <dl className="meta-grid">
          <div>
            <dt className="label">ID карты</dt>
            <dd>{card.id}</dd>
          </div>
          <div>
            <dt className="label">Статус</dt>
            <dd>
              <span className={`pill pill--${card.status === "ACTIVE" ? "success" : "warning"}`}>{card.status}</span>
            </dd>
          </div>
        </dl>
      </div>

      <div className="card">
        <div className="card__header">
          <div>
            <h3>Лимиты</h3>
            <p className="muted">Обновите дневные и месячные лимиты по карте.</p>
          </div>
        </div>
        <form className="form-grid" onSubmit={submitLimits}>
          {limitList.map((limit) => (
            <label key={limit.type} className="form-field">
              <span className="label">
                {limit.type} ({limit.window})
              </span>
              <input
                type="number"
                min={0}
                value={limitDraft[limit.type] ?? limit.value}
                onChange={(e) =>
                  setLimitDraft((prev) => ({
                    ...prev,
                    [limit.type]: Number(e.target.value),
                  }))
                }
              />
            </label>
          ))}
          <div className="form-actions">
            <button type="submit">Сохранить</button>
          </div>
        </form>
      </div>
    </div>
  );
}

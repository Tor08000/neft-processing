import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { blockCard, fetchCards, unblockCard } from "../api/cards";
import type { ClientCard } from "../types/cards";

export function ClientCardsPage() {
  const { user } = useAuth();
  const [cards, setCards] = useState<ClientCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);
    fetchCards(user)
      .then((data) => {
        if (!mounted) return;
        setCards(data.items);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
    return () => {
      mounted = false;
    };
  }, [user]);

  const toggleStatus = async (card: ClientCard) => {
    const confirmMessage =
      card.status === "ACTIVE"
        ? "Заблокировать карту?"
        : "Разблокировать карту?";
    if (typeof window !== "undefined" && !window.confirm(confirmMessage)) {
      return;
    }
    try {
      const response =
        card.status === "ACTIVE" ? await blockCard(card.id, user) : await unblockCard(card.id, user);
      setCards((prev) =>
        prev.map((c) => (c.id === card.id ? { ...c, status: response.status || c.status } : c)),
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Не удалось изменить статус";
      setError(message);
    }
  };

  if (isLoading) {
    return <div className="card">Загружаем карты...</div>;
  }

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Карты</h2>
          <p className="muted">Просмотр и управление выпущенными картами.</p>
        </div>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>ID карты</th>
            <th>Номер</th>
            <th>Статус</th>
            <th>Лимиты</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {cards.map((card) => (
            <tr key={card.id}>
              <td>{card.id}</td>
              <td>{card.pan_masked ?? "—"}</td>
              <td>
                <span className={`pill pill--${card.status === "ACTIVE" ? "success" : "warning"}`}>
                  {card.status}
                </span>
              </td>
              <td>
                {card.limits?.length ? (
                  <ul className="muted bullets compact">
                    {card.limits.map((limit) => (
                      <li key={`${limit.type}-${limit.window}`}>
                        {limit.type} ({limit.window}): {limit.value}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
              <td className="actions">
                <Link className="ghost" to={`/cards/${card.id}`}>
                  Подробнее
                </Link>
                <button type="button" className="secondary" onClick={() => void toggleStatus(card)}>
                  {card.status === "ACTIVE" ? "Заблокировать" : "Разблокировать"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

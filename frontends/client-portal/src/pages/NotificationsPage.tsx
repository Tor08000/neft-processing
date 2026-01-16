import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getClientNotificationsUnreadCount,
  listClientNotifications,
  markAllClientNotificationsRead,
  markClientNotificationRead,
  type ClientNotification,
} from "../api/clientNotifications";
import { useAuth } from "../auth/AuthContext";
import { formatDateTime } from "../utils/format";

const resolveBadgeClass = (severity: ClientNotification["severity"]) => {
  if (severity === "CRITICAL") return "badge badge-error";
  if (severity === "WARNING") return "badge badge-warning";
  return "badge badge-info";
};

export function NotificationsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState<ClientNotification[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState<number | null>(null);

  const loadNotifications = useCallback(
    async ({ cursor, reset }: { cursor?: string | null; reset?: boolean }) => {
      if (!user) return;
      if (reset) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }
      try {
        const response = await listClientNotifications(user, {
          unreadOnly,
          cursor: cursor ?? undefined,
          limit: 20,
        });
        setItems((prev) => (reset ? response.items : [...prev, ...response.items]));
        setNextCursor(response.next_cursor ?? null);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось загрузить уведомления");
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [unreadOnly, user],
  );

  useEffect(() => {
    void loadNotifications({ reset: true, cursor: null });
  }, [loadNotifications]);

  useEffect(() => {
    if (!user) return;
    getClientNotificationsUnreadCount(user)
      .then((response) => setUnreadCount(response.count))
      .catch(() => setUnreadCount(null));
  }, [user, items]);

  const handleMarkAll = async () => {
    if (!user) return;
    await markAllClientNotificationsRead(user, true);
    setItems((prev) => prev.map((item) => ({ ...item, read_at: item.read_at ?? new Date().toISOString() })));
    setUnreadCount(0);
  };

  const handleClick = async (item: ClientNotification) => {
    if (!user) return;
    if (!item.read_at) {
      try {
        await markClientNotificationRead(user, item.id);
        setItems((prev) =>
          prev.map((current) =>
            current.id === item.id ? { ...current, read_at: new Date().toISOString() } : current,
          ),
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось обновить уведомление");
      }
    }
    if (item.link) {
      navigate(item.link);
    }
  };

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Уведомления</h2>
            <p className="muted">Следите за событиями без ручной проверки.</p>
          </div>
          <div className="notification-actions">
            <label className="toggle">
              <input
                type="checkbox"
                checked={unreadOnly}
                onChange={(event) => {
                  setUnreadOnly(event.target.checked);
                  setNextCursor(null);
                }}
              />
              <span>Только непрочитанные</span>
            </label>
            <button type="button" className="neft-btn neft-btn-outline" onClick={handleMarkAll}>
              Пометить всё прочитанным
            </button>
          </div>
        </div>
      </div>

      {unreadCount !== null ? (
        <div className="muted small">Непрочитанных: {unreadCount}</div>
      ) : null}

      {error ? <div className="card state">{error}</div> : null}

      {loading ? (
        <div className="card">Загружаем уведомления…</div>
      ) : items.length === 0 ? (
        <div className="card">Уведомлений пока нет.</div>
      ) : (
        <div className="notification-list">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`notification-card ${item.read_at ? "" : "is-unread"}`}
              onClick={() => handleClick(item)}
            >
              <div className="notification-card__header">
                <span className={resolveBadgeClass(item.severity)}>{item.severity}</span>
                <span className="muted small">{formatDateTime(item.created_at)}</span>
              </div>
              <div className="notification-card__title">{item.title}</div>
              <div className="notification-card__body">{item.body}</div>
              {item.link ? <div className="notification-card__link">Открыть</div> : null}
            </button>
          ))}
        </div>
      )}

      {nextCursor ? (
        <button
          type="button"
          className="neft-btn neft-btn-outline"
          disabled={loadingMore}
          onClick={() => loadNotifications({ cursor: nextCursor })}
        >
          {loadingMore ? "Загружаем…" : "Показать ещё"}
        </button>
      ) : null}
    </div>
  );
}

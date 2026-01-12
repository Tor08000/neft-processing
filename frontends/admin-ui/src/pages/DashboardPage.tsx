import React, { useEffect, useState } from "react";
import { listUsers } from "../api/adminUsers";
import { useAuth } from "../auth/AuthContext";
import { ErrorState } from "../components/common/ErrorState";
import { Toast } from "../components/common/Toast";
import { useToast } from "../components/Toast/useToast";
import { AchievementBadge } from "../features/achievements/components/AchievementBadge";
import { StreakWidget } from "../features/achievements/components/StreakWidget";
import { useAchievements } from "../features/achievements/useAchievements";
import { KpiCard } from "../features/kpi/components/KpiCard";
import { KpiHintList } from "../features/kpi/components/KpiHintList";
import { useKpis } from "../features/kpi/useKpis";
import type { AdminUser } from "../types/users";

export const DashboardPage: React.FC = () => {
  const { user, accessToken, logout } = useAuth();
  const { toast, showToast } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const {
    kpis,
    hints,
    error: kpiError,
    isLoading: kpiLoading,
    reload: reloadKpis,
  } = useKpis({ showToast });
  const {
    badges,
    streak,
    error: achievementsError,
    isLoading: achievementsLoading,
    reload: reloadAchievements,
  } = useAchievements({ showToast });

  useEffect(() => {
    if (!accessToken) return;
    listUsers(accessToken)
      .then((data) => setUsers(data))
      .catch((err) => {
        console.error("Не удалось загрузить пользователей", err);
        setError("Не удалось загрузить данные пользователей");
        if (err instanceof Error && err.name === "UnauthorizedError") {
          logout();
        }
      });
  }, [accessToken, logout]);

  return (
    <div className="stack">
      <Toast toast={toast} />
      <div className="neft-card">
        <h2>Добро пожаловать, {user?.email}</h2>
        <p className="muted">Роль: {user?.roles.join(", ")}</p>
      </div>

      <div className="neft-card">
        <h3>Пользователи системы</h3>
        {error ? <div className="error-text">{error}</div> : null}
        <p>Загружено: {users.length}</p>
        <div className="pill-list">
          {users.slice(0, 5).map((item) => (
            <span key={item.id} className="pill">
              {item.email}
            </span>
          ))}
        </div>
      </div>

      <div className="neft-card">
        <h3>KPI за период</h3>
        <p className="muted">Операционные метрики по качеству и скорости исполнения.</p>
        {kpiError ? (
          <ErrorState
            title="Не удалось загрузить KPI"
            description={kpiError}
            actionLabel="Повторить"
            onAction={reloadKpis}
          />
        ) : kpiLoading ? (
          <p className="muted">Загрузка KPI...</p>
        ) : (
          <div className="kpi-grid">
            {kpis.map((kpi) => (
              <KpiCard key={kpi.id} {...kpi} />
            ))}
          </div>
        )}
      </div>

      <div className="neft-card">
        <h3>Прогресс и дисциплина</h3>
        {kpiError ? null : <KpiHintList hints={hints} />}
      </div>

      <div className="neft-card">
        <h3>Мониторинг</h3>
        <p className="muted">Секции для клиентских аккаунтов, операций и мониторинга появятся позже.</p>
      </div>

      <div className="neft-card">
        <h3>Badges & Streak</h3>
        {achievementsError ? (
          <ErrorState
            title="Не удалось загрузить достижения"
            description={achievementsError}
            actionLabel="Повторить"
            onAction={reloadAchievements}
          />
        ) : achievementsLoading ? (
          <p className="muted">Загрузка достижений...</p>
        ) : (
          <>
            <div className="achievement-grid">
              {badges.map((badge) => (
                <AchievementBadge key={badge.id} {...badge} />
              ))}
            </div>
            <div className="achievement-streak">
              <StreakWidget {...streak} />
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default DashboardPage;

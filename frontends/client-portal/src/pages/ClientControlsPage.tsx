import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { AppForbiddenState } from "../components/states";
import { ClientLimitsPage } from "./ClientLimitsPage";
import { ClientUsersPage } from "./ClientUsersPage";
import { ClientServicesPage } from "./ClientServicesPage";
import { ClientFeaturesPage } from "./ClientFeaturesPage";
import { hasAnyRole } from "../utils/roles";

const tabs = [
  { key: "limits", label: "Лимиты" },
  { key: "users", label: "Пользователи" },
  { key: "services", label: "Услуги и партнёры" },
  { key: "features", label: "Возможности" },
] as const;

type TabKey = (typeof tabs)[number]["key"];

export function ClientControlsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabKey>("limits");
  const canManageUsers = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация." />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Настройки / Управление</h2>
            <p className="muted">Изменения вступят в силу после проверки.</p>
            <p className="muted">Некоторые изменения требуют согласования.</p>
          </div>
        </div>
        <div className="tabs">
          {tabs
            .filter((tab) => (tab.key === "users" ? canManageUsers : true))
            .map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={activeTab === tab.key ? "primary" : "secondary"}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
        </div>
      </section>

      {activeTab === "limits" ? <ClientLimitsPage /> : null}
      {activeTab === "users" && canManageUsers ? <ClientUsersPage /> : null}
      {activeTab === "services" ? <ClientServicesPage /> : null}
      {activeTab === "features" ? <ClientFeaturesPage /> : null}
    </div>
  );
}

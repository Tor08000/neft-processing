import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { resolveClientWorkspace } from "../access/clientWorkspace";
import { AppForbiddenState } from "../components/states";
import { ClientLimitsPage } from "./ClientLimitsPage";
import { ClientUsersPage } from "./ClientUsersPage";
import { ClientServicesPage } from "./ClientServicesPage";
import { ClientFeaturesPage } from "./ClientFeaturesPage";
import { hasAnyRole } from "../utils/roles";

const tabs = [
  { key: "limits", label: "Лимиты" },
  { key: "users", label: "Пользователи" },
  { key: "services", label: "Услуги и партнеры" },
  { key: "features", label: "Возможности" },
] as const;

type TabKey = (typeof tabs)[number]["key"];

export function ClientControlsPage() {
  const { user } = useAuth();
  const { client } = useClient();
  const [activeTab, setActiveTab] = useState<TabKey>("limits");
  const workspace = resolveClientWorkspace({ client });
  const canManageUsers = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_ADMIN"]);

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация." />;
  }

  if (!workspace.hasTeamWorkspace) {
    return <AppForbiddenState message="Управление командой доступно только бизнес-клиентам с соответствующей ролью." />;
  }

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h2>Настройки / Управление</h2>
          <p className="muted">Изменения вступят в силу после проверки.</p>
          <p className="muted">Некоторые изменения требуют согласования.</p>
        </div>
      </div>
      <div className="surface-toolbar">
        <div className="toolbar-actions">
          {tabs
            .filter((tab) => (tab.key === "users" ? canManageUsers : true))
            .map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={activeTab === tab.key ? "primary" : "secondary"}
                aria-pressed={activeTab === tab.key}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
        </div>
      </div>

      {activeTab === "limits" ? <ClientLimitsPage /> : null}
      {activeTab === "users" && canManageUsers ? <ClientUsersPage /> : null}
      {activeTab === "services" ? <ClientServicesPage /> : null}
      {activeTab === "features" ? <ClientFeaturesPage /> : null}
    </div>
  );
}

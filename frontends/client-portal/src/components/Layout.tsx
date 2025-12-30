import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { CLIENT_BASE_PATH } from "../api/base";
import { hasAnyRole } from "../utils/roles";
import { AppErrorState } from "./states";

export function Layout() {
  const { user, logout } = useAuth();
  const apiBase = CLIENT_BASE_PATH ? null : "Отсутствует базовый путь клиента";
  const isApiBaseMissing = !import.meta.env.VITE_API_BASE && !import.meta.env.VITE_API_BASE_URL;
  const configError = isApiBaseMissing ? "App misconfigured: API base URL missing" : apiBase;

  if (configError) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <div className="topbar__meta">
            <span className="logo">NEFT</span>
            <div className="topbar__title">Client Portal</div>
          </div>
        </header>
        <main className="main-area">
          <AppErrorState message={configError} />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__meta">
          <span className="logo">NEFT</span>
          <div className="topbar__title">Client Portal</div>
          <div className="muted">{user?.clientId ? `Клиент ${user.clientId}` : "Клиентский кабинет"}</div>
        </div>
        <div className="topbar__meta topbar__meta--user">
          <div>
            <div className="muted">Вы вошли как</div>
            <strong>{user?.email}</strong>
            <div className="roles">{user?.roles.join(", ")}</div>
          </div>
          <button className="ghost" onClick={logout} type="button">
            Выйти
          </button>
        </div>
      </header>

      <div className="sidebar-layout">
        <nav className="sidebar">
          <NavLink to="/dashboard">Dashboard</NavLink>
          {(hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER"]) || !user) && (
            <NavLink to="/operations">Operations</NavLink>
          )}
          <NavLink to="/explain/insights">Explain Insights</NavLink>
          <NavLink to="/documents">Documents</NavLink>
          {(hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ACCOUNTANT"]) || !user) && (
            <NavLink to="/exports">Exports / 1C</NavLink>
          )}
          <NavLink to="/actions">Actions Center</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>

        <main className="main-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

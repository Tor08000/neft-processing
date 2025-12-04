import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__meta">
          <span className="topbar__title">NEFT Client Portal</span>
          <span className="muted">Демо-доступ к возможностям клиента</span>
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
          <NavLink to="/dashboard" end>
            Дашборд
          </NavLink>
          <span className="nav-disabled" aria-disabled>
            Операции (скоро)
          </span>
          <span className="nav-disabled" aria-disabled>
            Карты (скоро)
          </span>
          <span className="nav-disabled" aria-disabled>
            Лимиты (скоро)
          </span>
        </nav>

        <main className="main-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

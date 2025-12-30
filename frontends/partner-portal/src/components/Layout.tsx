import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__meta">
          <span className="logo">NEFT</span>
          <div className="topbar__title">Partner Portal</div>
          <div className="muted">{user?.partnerId ? `Партнёр ${user.partnerId}` : "Кабинет партнёра"}</div>
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
          <NavLink to="/" end>
            Дашборд
          </NavLink>
          <NavLink to="/stations">АЗС</NavLink>
          <NavLink to="/prices">Цены</NavLink>
          <NavLink to="/transactions">Операции</NavLink>
          <NavLink to="/payouts">Выплаты</NavLink>
          <NavLink to="/documents">Документы</NavLink>
          <NavLink to="/services">Сервисы</NavLink>
          <NavLink to="/integrations">Интеграции</NavLink>
          <NavLink to="/settings">Настройки</NavLink>
        </nav>

        <main className="main-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

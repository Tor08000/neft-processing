import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { user, logout } = useAuth();

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
          <NavLink to="/" end>
            Дашборд
          </NavLink>
          <NavLink to="/cards">Карты</NavLink>
          <div className="nav-section">Финансы</div>
          <NavLink to="/finance/invoices">Счета</NavLink>
          <NavLink to="/client/documents">Документы</NavLink>
          <NavLink to="/finance/reconciliation">Акт сверки</NavLink>
          <NavLink to="/finance/exports">Отчеты</NavLink>
          <NavLink to="/operations">Операции</NavLink>
          <NavLink to="/balances">Балансы</NavLink>
          <NavLink to="/profile">Профиль</NavLink>
        </nav>

        <main className="main-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

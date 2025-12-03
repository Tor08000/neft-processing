import { NavLink, Outlet } from "react-router-dom";
import type { ClientUser } from "../types";

interface LayoutProps {
  user?: ClientUser;
}

export function Layout({ user }: LayoutProps) {
  const orgName = user?.organization?.name ?? "NEFT Клиент";
  const userName = user?.fullName ?? "Гость";
  const role = user?.role ?? "VIEWER";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__meta">
          <span className="topbar__title">NEFT Client Portal</span>
          <span>{orgName}</span>
        </div>
        <div className="topbar__meta">
          <strong>{userName}</strong>
          <span className="badge pending">{role}</span>
        </div>
      </header>

      <div className="sidebar-layout">
        <nav className="sidebar">
          <NavLink to="/dashboard" end>
            Дашборд
          </NavLink>
          <NavLink to="/operations">Операции</NavLink>
          <NavLink to="/limits">Лимиты</NavLink>
        </nav>

        <main className="main-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

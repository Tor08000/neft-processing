import { Link } from "react-router-dom";
import type { ClientMode } from "../auth/clientModes";
import type { ClientNavItem } from "./ClientLayout";
import { Bell } from "../components/icons";

interface ClientTopbarProps {
  title: string;
  activePath: string;
  items: ClientNavItem[];
  userEmail?: string | null;
  mode: ClientMode;
  availableModes: ClientMode[];
  theme: "light" | "dark";
  onSelectMode: (mode: ClientMode) => void;
  onToggleTheme: () => void;
  onToggleSidebar: () => void;
  onLogout: () => void;
}

const getSectionLabel = (activePath: string, items: ClientNavItem[]) => {
  const match = items.find((item) =>
    activePath === item.to || (item.to !== "/" && activePath.startsWith(`${item.to}/`)),
  );
  return match?.label ?? "Обзор";
};

const MODE_LABELS: Record<ClientMode, string> = {
  fleet: "Автопарк",
  personal: "Частник",
};

export function ClientTopbar({
  title,
  activePath,
  items,
  userEmail,
  mode,
  availableModes,
  theme,
  onSelectMode,
  onToggleTheme,
  onToggleSidebar,
  onLogout,
}: ClientTopbarProps) {
  const sectionLabel = getSectionLabel(activePath, items);
  const themeLabel = theme === "dark" ? "Тёмная" : "Светлая";
  const modeLabel = MODE_LABELS[mode];

  return (
    <header className="neftc-topbar">
      <div className="neftc-topbar__left">
        <button
          type="button"
          className="neftc-topbar__menu"
          aria-label="Свернуть боковую панель"
          onClick={onToggleSidebar}
        >
          ☰
        </button>
        <div className="neftc-topbar__title">
          <div className="neftc-topbar__title-main">{title}</div>
          <div className="neftc-topbar__title-subtitle">{sectionLabel}</div>
        </div>
      </div>
      <div className="neftc-topbar__search-wrap">
        <input
          type="search"
          className="neftc-topbar__search neftc-input"
          placeholder="Поиск по кабинету"
          aria-label="Поиск"
        />
      </div>
      <div className="neftc-topbar__actions">
        <Link to="/client/notifications" className="neftc-icon-button" aria-label="Уведомления">
          <Bell size={18} />
        </Link>
        <button type="button" className="neftc-pill" onClick={onToggleTheme}>
          Тема: {themeLabel}
        </button>
        {availableModes.length > 1 ? (
          <label className="neftc-pill" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            Режим:
            <select
              aria-label="Режим клиента"
              value={mode}
              onChange={(event) => onSelectMode(event.target.value as ClientMode)}
              className="neft-input"
            >
              {availableModes.map((item) => (
                <option key={item} value={item}>
                  {MODE_LABELS[item]}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div className="neftc-topbar__profile">
          <div className="neftc-topbar__profile-meta">
            <div className="neftc-topbar__profile-name">{userEmail ?? "user@neft.app"}</div>
            <div className="neftc-topbar__profile-role">{modeLabel}</div>
          </div>
          <button type="button" className="neftc-link" onClick={onLogout}>
            Выйти
          </button>
        </div>
      </div>
    </header>
  );
}

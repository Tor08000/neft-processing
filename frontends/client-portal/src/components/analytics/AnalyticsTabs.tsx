import { NavLink } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useI18n } from "../../i18n";
import { canAccessFinance } from "../../utils/roles";

export function AnalyticsTabs() {
  const { user } = useAuth();
  const { t } = useI18n();
  const financeAccess = canAccessFinance(user);

  return (
    <div className="tabs analytics-tabs">
      <NavLink to="/analytics" end className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
        {t("analytics.tabs.overview")}
      </NavLink>
      <NavLink to="/analytics/spend" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
        {t("analytics.tabs.spend")}
      </NavLink>
      <NavLink to="/analytics/declines" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
        {t("analytics.tabs.declines")}
      </NavLink>
      <NavLink to="/analytics/marketplace" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
        {t("analytics.tabs.marketplace")}
      </NavLink>
      <NavLink to="/analytics/documents" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
        {t("analytics.tabs.documents")}
      </NavLink>
      {financeAccess ? (
        <NavLink to="/analytics/exports" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
          {t("analytics.tabs.exports")}
        </NavLink>
      ) : null}
    </div>
  );
}

import { NavLink, useLocation } from "react-router-dom";
import { useI18n } from "../i18n";

export function PolicyCenterTabs() {
  const { t } = useI18n();
  const location = useLocation();
  const isRulesActive =
    location.pathname.startsWith("/fleet/policy-center/actions") ||
    location.pathname.startsWith("/fleet/policy-center/notifications");

  return (
    <div className="tabs policy-center-tabs">
      <NavLink to="/fleet/policy-center/actions" className={`tab ${isRulesActive ? "active" : ""}`}>
        {t("policyCenter.tabs.rules")}
      </NavLink>
      <NavLink to="/fleet/policy-center/channels" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
        {t("policyCenter.tabs.channels")}
      </NavLink>
      <NavLink to="/fleet/policy-center/executions" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
        {t("policyCenter.tabs.executions")}
      </NavLink>
    </div>
  );
}

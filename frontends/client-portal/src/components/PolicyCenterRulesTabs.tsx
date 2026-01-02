import { NavLink } from "react-router-dom";
import { useI18n } from "../i18n";

export function PolicyCenterRulesTabs() {
  const { t } = useI18n();

  return (
    <div className="tabs policy-center-rules-tabs">
      <NavLink to="/fleet/policy-center/actions" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
        {t("policyCenter.rulesTabs.actions")}
      </NavLink>
      <NavLink to="/fleet/policy-center/notifications" className={({ isActive }) => `tab ${isActive ? "active" : ""}`}>
        {t("policyCenter.rulesTabs.notifications")}
      </NavLink>
    </div>
  );
}

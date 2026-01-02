import { AppEmptyState } from "./states";
import { useI18n } from "../i18n";

export function FleetUnavailableState() {
  const { t } = useI18n();
  return <AppEmptyState title={t("fleet.errors.unavailableTitle")} description={t("fleet.errors.unavailableDescription")} />;
}

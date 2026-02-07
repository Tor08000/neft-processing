import { useAuth } from "../../auth/AuthContext";
import { isDemoPartner } from "@shared/demo/demo";
import { AnalyticsPageDemo } from "./AnalyticsPageDemo";
import { AnalyticsPageProd } from "./AnalyticsPageProd";

export function AnalyticsPage() {
  const { user } = useAuth();
  const demo = isDemoPartner(user?.email ?? null);

  return demo ? <AnalyticsPageDemo /> : <AnalyticsPageProd />;
}

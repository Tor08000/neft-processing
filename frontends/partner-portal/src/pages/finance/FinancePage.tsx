import { useAuth } from "../../auth/AuthContext";
import { isDemoPartner } from "@shared/demo/demo";
import { FinancePageDemo } from "./FinancePageDemo";
import { FinancePageProd } from "./FinancePageProd";

export function FinancePage() {
  const { user } = useAuth();
  const demo = isDemoPartner(user?.email ?? null);

  return demo ? <FinancePageDemo /> : <FinancePageProd />;
}

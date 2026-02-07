import { useAuth } from "../../auth/AuthContext";
import { isDemoPartner } from "@shared/demo/demo";
import { PayoutsPageDemo } from "./PayoutsPageDemo";
import { PayoutsPageProd } from "./PayoutsPageProd";

export function PayoutsPage() {
  const { user } = useAuth();
  const demo = isDemoPartner(user?.email ?? null);

  return demo ? <PayoutsPageDemo /> : <PayoutsPageProd />;
}

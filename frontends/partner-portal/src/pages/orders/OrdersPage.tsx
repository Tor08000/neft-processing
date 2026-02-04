import { useAuth } from "../../auth/AuthContext";
import { isDemoPartner } from "@shared/demo/demo";
import { OrdersPageDemo } from "./OrdersPageDemo";
import { OrdersPageProd } from "./OrdersPageProd";

export function OrdersPage() {
  const { user } = useAuth();
  const demo = isDemoPartner(user?.email ?? null);

  return demo ? <OrdersPageDemo /> : <OrdersPageProd />;
}

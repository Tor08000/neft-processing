import { useAuth } from "../../auth/AuthContext";
import { isDemoPartner } from "@shared/demo/demo";
import { ServicesCatalogPageDemo } from "./ServicesCatalogPageDemo";
import { ServicesCatalogPageProd } from "./ServicesCatalogPageProd";

export function ServicesCatalogPage() {
  const { user } = useAuth();
  const demo = isDemoPartner(user?.email ?? null);

  return demo ? <ServicesCatalogPageDemo /> : <ServicesCatalogPageProd />;
}

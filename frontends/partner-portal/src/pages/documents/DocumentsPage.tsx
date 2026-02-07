import { useAuth } from "../../auth/AuthContext";
import { isDemoPartner } from "@shared/demo/demo";
import { DocumentsPageDemo } from "./DocumentsPageDemo";
import { DocumentsPageProd } from "./DocumentsPageProd";

export function DocumentsPage() {
  const { user } = useAuth();
  const demo = isDemoPartner(user?.email ?? null);

  return demo ? <DocumentsPageDemo /> : <DocumentsPageProd />;
}

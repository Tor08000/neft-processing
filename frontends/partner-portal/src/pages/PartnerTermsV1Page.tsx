import { useEffect, useState } from "react";
import { fetchPartnerTermsV1, type PartnerTermsV1 } from "../api/partner";
import { useAuth } from "../auth/AuthContext";

export function PartnerTermsV1Page() {
  const { user } = useAuth();
  const [terms, setTerms] = useState<PartnerTermsV1 | null>(null);

  useEffect(() => {
    if (!user) return;
    fetchPartnerTermsV1(user.token).then(setTerms).catch(() => setTerms(null));
  }, [user]);

  return (
    <section className="card stack">
      <h2>Условия</h2>
      {!terms || Object.keys(terms.terms ?? {}).length === 0 ? (
        <p className="muted">Нет активных условий.</p>
      ) : (
        <pre>{JSON.stringify(terms.terms, null, 2)}</pre>
      )}
    </section>
  );
}

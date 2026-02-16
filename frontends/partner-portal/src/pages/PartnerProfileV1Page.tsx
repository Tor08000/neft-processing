import { useEffect, useState } from "react";
import { fetchPartnerMeV1, patchPartnerMeV1 } from "../api/partner";
import { useAuth } from "../auth/AuthContext";

export function PartnerProfileV1Page() {
  const { user } = useAuth();
  const [data, setData] = useState<{ brand_name?: string | null; contacts?: Record<string, unknown> } | null>(null);

  useEffect(() => {
    if (!user) return;
    fetchPartnerMeV1(user.token).then((res) => setData({ brand_name: res.partner.brand_name, contacts: res.partner.contacts ?? {} }));
  }, [user]);

  if (!user || !data) return <div className="card">Загрузка...</div>;

  return (
    <section className="card stack">
      <h2>Профиль партнёра</h2>
      <label>
        Бренд
        <input
          value={data.brand_name ?? ""}
          onChange={(e) => setData((prev) => ({ ...(prev ?? {}), brand_name: e.target.value }))}
        />
      </label>
      <label>
        Контакты (JSON)
        <textarea
          rows={8}
          value={JSON.stringify(data.contacts ?? {}, null, 2)}
          onChange={(e) => {
            try {
              setData((prev) => ({ ...(prev ?? {}), contacts: JSON.parse(e.target.value) }));
            } catch {
              // keep last valid json
            }
          }}
        />
      </label>
      <button
        type="button"
        onClick={async () => {
          await patchPartnerMeV1(user.token, { brand_name: data.brand_name ?? undefined, contacts: data.contacts ?? {} });
        }}
      >
        Сохранить
      </button>
    </section>
  );
}

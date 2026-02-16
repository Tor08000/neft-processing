import { useEffect, useState } from "react";
import { createPartnerLocationV1, deactivatePartnerLocationV1, fetchPartnerLocationsV1, type PartnerLocationV1 } from "../api/partner";
import { useAuth } from "../auth/AuthContext";

export function PartnerLocationsV1Page() {
  const { user } = useAuth();
  const [items, setItems] = useState<PartnerLocationV1[]>([]);

  const load = async () => {
    if (!user) return;
    setItems(await fetchPartnerLocationsV1(user.token));
  };

  useEffect(() => {
    void load();
  }, [user]);

  if (!user) return null;

  return (
    <section className="card stack">
      <h2>Точки / АЗС</h2>
      <button
        type="button"
        onClick={async () => {
          await createPartnerLocationV1(user.token, { title: "Новая точка", address: "Адрес" });
          await load();
        }}
      >
        Добавить точку
      </button>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            {item.title} — {item.address} ({item.status}){" "}
            <button
              type="button"
              onClick={async () => {
                await deactivatePartnerLocationV1(user.token, item.id);
                await load();
              }}
            >
              Деактивировать
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

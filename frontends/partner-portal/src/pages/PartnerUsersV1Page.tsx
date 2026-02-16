import { useEffect, useState } from "react";
import { addPartnerUserV1, fetchPartnerMeV1, fetchPartnerUsersV1, removePartnerUserV1 } from "../api/partner";
import { useAuth } from "../auth/AuthContext";

export function PartnerUsersV1Page() {
  const { user } = useAuth();
  const [users, setUsers] = useState<{ user_id: string; roles: string[] }[]>([]);
  const [isOwner, setIsOwner] = useState(false);

  const load = async () => {
    if (!user) return;
    const me = await fetchPartnerMeV1(user.token);
    setIsOwner((me.my_roles ?? []).includes("PARTNER_OWNER"));
    setUsers(await fetchPartnerUsersV1(user.token));
  };

  useEffect(() => {
    void load();
  }, [user]);

  if (!user) return null;

  return (
    <section className="card stack">
      <h2>Пользователи партнёра</h2>
      {isOwner ? (
        <button
          type="button"
          onClick={async () => {
            await addPartnerUserV1(user.token, { user_id: `user-${Date.now()}`, roles: ["PARTNER_MANAGER"] });
            await load();
          }}
        >
          Добавить пользователя
        </button>
      ) : (
        <p className="muted">Только PARTNER_OWNER может управлять пользователями.</p>
      )}
      <ul>
        {users.map((item) => (
          <li key={item.user_id}>
            {item.user_id} ({item.roles.join(", ")})
            {isOwner ? (
              <button
                type="button"
                onClick={async () => {
                  await removePartnerUserV1(user.token, item.user_id);
                  await load();
                }}
              >
                Удалить
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

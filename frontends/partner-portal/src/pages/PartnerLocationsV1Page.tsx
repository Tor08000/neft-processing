import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  createPartnerLocationV1,
  deactivatePartnerLocationV1,
  fetchPartnerLocationsV1,
  type PartnerLocationV1,
} from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { canManagePartnerLocations } from "../access/partnerWorkspace";
import { ErrorState, LoadingState } from "../components/states";
import { PartnerSupportActions } from "../components/PartnerSupportActions";

export function PartnerLocationsV1Page() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const canManage = canManagePartnerLocations(portal, user?.roles);
  const [items, setItems] = useState<PartnerLocationV1[]>([]);
  const [title, setTitle] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      setItems(await fetchPartnerLocationsV1(user.token));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить локации.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [user]);

  if (!user) return null;
  if (loading) return <LoadingState label="Загружаем локации..." />;
  if (error) return <ErrorState description={error} />;

  const handleCreate = async () => {
    if (!title.trim() || !address.trim()) return;
    setSaving(true);
    setActionError(null);
    try {
      await createPartnerLocationV1(user.token, {
        title: title.trim(),
        address: address.trim(),
        city: city.trim() || undefined,
      });
      setTitle("");
      setAddress("");
      setCity("");
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось создать локацию.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (id: string) => {
    setActionError(null);
    try {
      await deactivatePartnerLocationV1(user.token, id);
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось деактивировать локацию.");
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Точки и локации</h2>
            <p className="muted">Операционный список локаций для сервисных, fuel и logistics партнёров.</p>
          </div>
          <div className="actions">
            <Link className="ghost" to="/partner/profile">
              Профиль
            </Link>
            <Link className="ghost" to="/support/requests">
              Обращения
            </Link>
          </div>
        </div>
        {canManage ? (
          <div className="card__section">
            <div className="grid three">
              <label className="filter">
                Название
                <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="АЗС №12" />
              </label>
              <label className="filter">
                Адрес
                <input value={address} onChange={(event) => setAddress(event.target.value)} placeholder="Москва, ул. Пример, 1" />
              </label>
              <label className="filter">
                Город
                <input value={city} onChange={(event) => setCity(event.target.value)} placeholder="Москва" />
              </label>
            </div>
            <div className="actions">
              <button type="button" className="primary" onClick={() => void handleCreate()} disabled={saving || !title.trim() || !address.trim()}>
                {saving ? "Сохраняем..." : "Добавить локацию"}
              </button>
            </div>
            {actionError ? <div className="notice error">{actionError}</div> : null}
          </div>
        ) : (
          <div className="notice">Режим только для чтения. Менять локации могут owner и manager.</div>
        )}

        {items.length === 0 ? (
          <div className="card__section">
            <p className="muted">Локации ещё не заведены.</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Название</th>
                <th>Адрес</th>
                <th>Город</th>
                <th>Статус</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.title}</td>
                  <td>{item.address}</td>
                  <td>{item.city ?? "—"}</td>
                  <td>{item.status}</td>
                  <td>
                    {canManage ? (
                      <button type="button" className="ghost" onClick={() => void handleDeactivate(item.id)} disabled={item.status === "INACTIVE"}>
                        Деактивировать
                      </button>
                    ) : (
                      <span className="muted">Просмотр</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <PartnerSupportActions
        title="Нужна помощь по локациям?"
        description="Создайте support case, если локация не видна в booking/order контуре или её статус расходится с runtime truth."
        requestTitle="Нужна помощь по локациям партнёра"
        relatedLinks={[
          { to: "/support/requests", label: "История обращений" },
          { to: "/partner/profile", label: "Профиль" },
        ]}
      />
    </div>
  );
}

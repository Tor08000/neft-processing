import { useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import {
  fetchPartnerLegalPackHistory,
  fetchPartnerLegalProfile,
  generatePartnerLegalPack,
  updatePartnerLegalStatus,
  type PartnerLegalPack,
  type PartnerLegalProfileAdmin,
} from "../../api/partnerLegal";
import AdminWriteActionModal from "../../components/admin/AdminWriteActionModal";
import { useAdmin } from "../../admin/AdminContext";

export default function PartnerLegalPage() {
  const { accessToken } = useAuth();
  const { profile: adminProfile } = useAdmin();
  const [partnerId, setPartnerId] = useState("");
  const [profile, setProfile] = useState<PartnerLegalProfileAdmin | null>(null);
  const [packs, setPacks] = useState<PartnerLegalPack[]>([]);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingStatus, setPendingStatus] = useState<string | null>(null);
  const canWrite = Boolean(adminProfile?.permissions.legal?.write) && !adminProfile?.read_only;

  const loadProfile = async () => {
    if (!accessToken || !partnerId.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchPartnerLegalProfile(accessToken, partnerId.trim());
      setProfile(data);
      const history = await fetchPartnerLegalPackHistory(accessToken, partnerId.trim());
      setPacks(history);
    } catch (err) {
      console.error(err);
      setError("Не удалось загрузить юридический профиль");
    } finally {
      setIsLoading(false);
    }
  };

  const updateStatus = async (status: string, reason: string, correlationId: string) => {
    if (!accessToken || !partnerId.trim()) return;
    if (!canWrite) return;
    setIsLoading(true);
    setError(null);
    try {
      const updated = await updatePartnerLegalStatus(accessToken, partnerId.trim(), {
        status,
        reason,
        correlation_id: correlationId,
        comment,
      });
      setProfile(updated);
      setComment("");
    } catch (err) {
      console.error(err);
      setError("Не удалось обновить статус");
    } finally {
      setIsLoading(false);
    }
  };

  const generatePack = async () => {
    if (!accessToken || !partnerId.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      await generatePartnerLegalPack(accessToken, partnerId.trim(), "ZIP");
      const history = await fetchPartnerLegalPackHistory(accessToken, partnerId.trim());
      setPacks(history);
    } catch (err) {
      console.error(err);
      setError("Не удалось сформировать пакет");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Partner Legal Profile</h2>
        </div>
        <div className="form-grid">
          <label className="field">
            <span className="label">Partner ID</span>
            <input value={partnerId} onChange={(event) => setPartnerId(event.target.value)} placeholder="partner_id" />
          </label>
          <div className="field">
            <button className="primary" type="button" onClick={loadProfile} disabled={isLoading}>
              {isLoading ? "Загрузка..." : "Загрузить"}
            </button>
          </div>
        </div>
        {error ? <div className="error">{error}</div> : null}
      </section>

      {profile ? (
        <>
          <section className="card">
            <div className="section-title">
              <h2>Статус и реквизиты</h2>
            </div>
            <div className="grid-2">
              <div>
                <div className="muted">Статус</div>
                <div style={{ fontWeight: 700 }}>{profile.legal_status ?? "—"}</div>
              </div>
              <div>
                <div className="muted">Тип</div>
                <div>{profile.legal_type ?? "—"}</div>
              </div>
              <div>
                <div className="muted">Режим</div>
                <div>{profile.tax_regime ?? "—"}</div>
              </div>
              <div>
                <div className="muted">НДС</div>
                <div>{profile.vat_applicable ? `Да (${profile.vat_rate ?? 0}%)` : "Нет"}</div>
              </div>
            </div>
            {profile.details ? (
              <div className="meta-grid" style={{ marginTop: "1rem" }}>
                {Object.entries(profile.details).map(([key, value]) => (
                  <div key={key}>
                    <div className="muted">{key}</div>
                    <div>{value ? String(value) : "—"}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="muted" style={{ marginTop: "1rem" }}>
                Реквизиты не заполнены.
              </div>
            )}
          </section>

          <section className="card">
            <div className="section-title">
              <h2>Верификация</h2>
            </div>
            <label className="field">
              <span className="label">Комментарий</span>
              <input value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Комментарий" />
            </label>
            <div className="button-row" style={{ marginTop: "1rem" }}>
              <button
                className="primary"
                type="button"
                onClick={() => setPendingStatus("VERIFIED")}
                disabled={isLoading || !canWrite}
              >
                Подтвердить
              </button>
              <button
                className="ghost"
                type="button"
                onClick={() => setPendingStatus("BLOCKED")}
                disabled={isLoading || !canWrite}
              >
                Заблокировать
              </button>
              <button
                className="ghost"
                type="button"
                onClick={() => setPendingStatus("PENDING_REVIEW")}
                disabled={isLoading || !canWrite}
              >
                На проверку
              </button>
              {!canWrite ? <span className="muted">Read-only mode enabled</span> : null}
            </div>
          </section>

          <section className="card">
            <div className="section-title">
              <h2>Legal Pack</h2>
            </div>
            <button className="primary" type="button" onClick={generatePack} disabled={isLoading}>
              Сформировать пакет
            </button>
            {packs.length ? (
              <table className="data-table" style={{ marginTop: "1rem" }}>
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Формат</th>
                    <th>Хэш</th>
                    <th>Ссылка</th>
                  </tr>
                </thead>
                <tbody>
                  {packs.map((pack) => (
                    <tr key={pack.id}>
                      <td>{new Date(pack.created_at).toLocaleString("ru-RU")}</td>
                      <td>{pack.format}</td>
                      <td>{pack.pack_hash.slice(0, 8)}</td>
                      <td>{pack.download_url ? <a href={pack.download_url}>Скачать</a> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="muted" style={{ marginTop: "1rem" }}>
                История пакетов пуста.
              </div>
            )}
          </section>
        </>
      ) : null}

      <AdminWriteActionModal
        isOpen={pendingStatus !== null}
        title="Confirm legal status change"
        requirePhrase
        confirmPhrase="CONFIRM"
        onConfirm={({ reason, correlationId }) => {
          if (!pendingStatus) return;
          return updateStatus(pendingStatus, reason, correlationId).finally(() => setPendingStatus(null));
        }}
        onCancel={() => setPendingStatus(null)}
      />
    </div>
  );
}

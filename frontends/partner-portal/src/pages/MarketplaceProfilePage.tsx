import { useEffect, useState } from "react";
import { fetchMarketplaceProfile, upsertMarketplaceProfile } from "../api/marketplaceCatalog";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { useTranslation } from "react-i18next";
import type { MarketplacePartnerProfile } from "../types/marketplace";

export function MarketplaceProfilePage() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [profile, setProfile] = useState<MarketplacePartnerProfile | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchMarketplaceProfile(user.token)
      .then((data) => {
        if (!active) return;
        setProfile(data);
        setCompanyName(data.company_name ?? "");
        setDescription(data.description ?? "");
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiError && err.status === 404) {
          setProfile(null);
          setCompanyName("");
          setDescription("");
          return;
        }
        setError(t("marketplace.profile.loadError"));
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [user, t]);

  const handleSubmit = async () => {
    if (!user) return;
    setIsSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await upsertMarketplaceProfile(user.token, {
        company_name: companyName.trim(),
        description: description.trim() || null,
      });
      setProfile(updated);
      setSuccess(t("marketplace.profile.saved"));
    } catch (err) {
      console.error(err);
      setError(t("marketplace.profile.saveError"));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("marketplace.profile.title")}</h2>
            <p className="muted">{t("marketplace.profile.subtitle")}</p>
          </div>
          {profile?.verification_status ? (
            <StatusBadge status={profile.verification_status} />
          ) : null}
        </div>
        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : (
          <div className="stack">
            <div className="form-grid">
              <label className="form-field">
                <span className="label">{t("marketplace.profile.fields.companyName")}</span>
                <input
                  type="text"
                  value={companyName}
                  onChange={(event) => setCompanyName(event.target.value)}
                  placeholder={t("marketplace.profile.fields.companyNamePlaceholder")}
                />
              </label>
              <label className="form-field">
                <span className="label">{t("marketplace.profile.fields.description")}</span>
                <textarea
                  rows={4}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder={t("marketplace.profile.fields.descriptionPlaceholder")}
                />
              </label>
            </div>
            <div className="muted">{t("marketplace.profile.verificationInfo")}</div>
            {error ? (
              <div className="error" role="alert">
                {error}
              </div>
            ) : null}
            {success ? <div className="success" role="status">{success}</div> : null}
            <div className="actions">
              <button type="button" className="primary" onClick={handleSubmit} disabled={isSaving || !companyName.trim()}>
                {isSaving ? t("marketplace.profile.saving") : t("actions.save")}
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

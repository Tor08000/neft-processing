import { useEffect, useMemo, useState } from "react";
import {
  archiveMarketplaceOffer,
  createMarketplaceOffer,
  fetchMarketplaceOffer,
  fetchMarketplaceOffers,
  submitMarketplaceOffer,
  updateMarketplaceOffer,
} from "../api/marketplaceOffers";
import type {
  MarketplaceOffer,
  MarketplaceOfferEntitlementScope,
  MarketplaceOfferGeoScope,
  MarketplaceOfferPriceModel,
  MarketplaceOfferSubjectType,
  MarketplaceOfferSummary,
} from "../types/marketplace";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate } from "../utils/format";
import { useTranslation } from "react-i18next";
import { EmptyState } from "@shared/ui/EmptyState";
import { PartnerErrorState } from "../components/PartnerErrorState";

const defaultFormState = {
  subject_type: "PRODUCT" as MarketplaceOfferSubjectType,
  subject_id: "",
  title_override: "",
  currency: "RUB",
  price_model: "FIXED" as MarketplaceOfferPriceModel,
  price_amount: "",
  price_min: "",
  price_max: "",
  geo_scope: "ALL_PARTNER_LOCATIONS" as MarketplaceOfferGeoScope,
  location_ids: "",
  region_code: "",
  entitlement_scope: "ALL_CLIENTS" as MarketplaceOfferEntitlementScope,
  allowed_subscription_codes: "",
  allowed_client_ids: "",
  valid_from: "",
  valid_to: "",
};

type FormState = typeof defaultFormState;

const parseList = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const mapOfferToForm = (offer: MarketplaceOffer): FormState => ({
  subject_type: offer.subject_type,
  subject_id: offer.subject_id,
  title_override: offer.title_override ?? "",
  currency: offer.currency,
  price_model: offer.price_model,
  price_amount: offer.price_amount?.toString() ?? "",
  price_min: offer.price_min?.toString() ?? "",
  price_max: offer.price_max?.toString() ?? "",
  geo_scope: offer.geo_scope,
  location_ids: (offer.location_ids ?? []).join(", "),
  region_code: offer.region_code ?? "",
  entitlement_scope: offer.entitlement_scope,
  allowed_subscription_codes: (offer.allowed_subscription_codes ?? []).join(", "),
  allowed_client_ids: (offer.allowed_client_ids ?? []).join(", "),
  valid_from: offer.valid_from ?? "",
  valid_to: offer.valid_to ?? "",
});

export function MarketplaceOffersPage() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [items, setItems] = useState<MarketplaceOfferSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("");
  const [query, setQuery] = useState("");
  const [form, setForm] = useState<FormState>(defaultFormState);
  const [editing, setEditing] = useState<MarketplaceOffer | null>(null);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [actionError, setActionError] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      status: statusFilter || undefined,
      subject_type: subjectFilter || undefined,
      q: query || undefined,
    }),
    [statusFilter, subjectFilter, query],
  );

  const loadOffers = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchMarketplaceOffers(user.token, filters)
      .then((data) => setItems(data.items ?? []))
      .catch(setError)
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadOffers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, filters.status, filters.subject_type, filters.q]);

  const resetForm = () => {
    setEditing(null);
    setForm(defaultFormState);
    setFormErrors({});
  };

  const validateForm = () => {
    const errors: Record<string, string> = {};
    if (!form.subject_id.trim()) {
      errors.subject_id = "required";
    }
    if (!form.currency.trim()) {
      errors.currency = "required";
    }
    if (form.price_model === "RANGE") {
      if (!form.price_min || !form.price_max) {
        errors.price_range = "required";
      }
    } else if (!form.price_amount) {
      errors.price_amount = "required";
    }
    if (form.geo_scope === "SELECTED_LOCATIONS" && !parseList(form.location_ids).length) {
      errors.location_ids = "required";
    }
    if (form.geo_scope === "REGION" && !form.region_code.trim()) {
      errors.region_code = "required";
    }
    if (form.entitlement_scope === "SUBSCRIPTION_ONLY" && !parseList(form.allowed_subscription_codes).length) {
      errors.allowed_subscription_codes = "required";
    }
    if (form.entitlement_scope === "SEGMENT_ONLY" && !parseList(form.allowed_client_ids).length) {
      errors.allowed_client_ids = "required";
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const buildPayload = () => ({
    subject_type: form.subject_type,
    subject_id: form.subject_id.trim(),
    title_override: form.title_override.trim() || undefined,
    currency: form.currency.trim(),
    price_model: form.price_model,
    price_amount: form.price_amount ? Number(form.price_amount) : undefined,
    price_min: form.price_min ? Number(form.price_min) : undefined,
    price_max: form.price_max ? Number(form.price_max) : undefined,
    terms: {},
    geo_scope: form.geo_scope,
    location_ids: parseList(form.location_ids),
    region_code: form.region_code.trim() || undefined,
    entitlement_scope: form.entitlement_scope,
    allowed_subscription_codes: parseList(form.allowed_subscription_codes),
    allowed_client_ids: parseList(form.allowed_client_ids),
    valid_from: form.valid_from || undefined,
    valid_to: form.valid_to || undefined,
  });

  const handleSave = async () => {
    if (!user) return;
    setActionError(null);
    if (!validateForm()) {
      setActionError(t("marketplace.offers.validation"));
      return;
    }
    try {
      if (editing) {
        const response = await updateMarketplaceOffer(user.token, editing.id, buildPayload());
        setEditing(response.data);
      } else {
        await createMarketplaceOffer(user.token, buildPayload());
      }
      resetForm();
      loadOffers();
    } catch {
      setActionError(t("common.unavailableDescription"));
    }
  };

  const handleEdit = (offer: MarketplaceOfferSummary) => {
    if (!user) return;
    fetchMarketplaceOffer(user.token, offer.id)
      .then((response) => {
        const full = response as unknown as MarketplaceOffer;
        setEditing(full);
        setForm(mapOfferToForm(full));
      })
      .catch(() => setActionError(t("common.unavailableDescription")));
  };

  const handleSubmit = async (offerId: string) => {
    if (!user) return;
    if (!window.confirm(t("marketplace.offers.confirmSubmit"))) return;
    await submitMarketplaceOffer(user.token, offerId);
    loadOffers();
  };

  const handleArchive = async (offerId: string) => {
    if (!user) return;
    if (!window.confirm(t("marketplace.offers.confirmArchive"))) return;
    await archiveMarketplaceOffer(user.token, offerId);
    loadOffers();
  };

  return (
    <div className="page-grid">
      <section className="card">
        <header className="section-header">
          <div>
            <h2>{t("marketplace.offers.title")}</h2>
            <p className="muted">{t("marketplace.offers.subtitle")}</p>
          </div>
        </header>

        <div className="filters">
          <label className="field">
            <span>{t("common.status")}</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">{t("common.all")}</option>
              <option value="DRAFT">DRAFT</option>
              <option value="PENDING_REVIEW">PENDING_REVIEW</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="SUSPENDED">SUSPENDED</option>
              <option value="ARCHIVED">ARCHIVED</option>
            </select>
          </label>
          <label className="field">
            <span>{t("marketplace.offers.filters.subject")}</span>
            <select value={subjectFilter} onChange={(event) => setSubjectFilter(event.target.value)}>
              <option value="">{t("common.all")}</option>
              <option value="PRODUCT">PRODUCT</option>
              <option value="SERVICE">SERVICE</option>
            </select>
          </label>
          <label className="field">
            <span>{t("common.search")}</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("common.search")} />
          </label>
        </div>

        {isLoading ? (
          <div className="muted">{t("common.loading")}</div>
        ) : error ? (
          <PartnerErrorState />
        ) : items.length === 0 ? (
          <EmptyState title={t("marketplace.offers.emptyTitle")} description={t("marketplace.offers.emptyDescription")} />
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("marketplace.offers.table.subject")}</th>
                  <th>{t("marketplace.offers.table.price")}</th>
                  <th>{t("marketplace.offers.table.geo")}</th>
                  <th>{t("marketplace.offers.table.entitlements")}</th>
                  <th>{t("common.status")}</th>
                  <th>{t("marketplace.offers.table.validity")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((offer) => (
                  <tr key={offer.id}>
                    <td>
                      <div className="muted">{offer.subject_type}</div>
                      <div>{offer.title_override || offer.subject_id}</div>
                    </td>
                    <td>
                      <div>{offer.price_model}</div>
                      <div className="muted">{offer.currency}</div>
                    </td>
                    <td>{offer.geo_scope}</td>
                    <td>{offer.entitlement_scope}</td>
                    <td>
                      <StatusBadge status={offer.status} />
                    </td>
                    <td>
                      <div>{offer.valid_from ? formatDate(offer.valid_from) : "—"}</div>
                      <div>{offer.valid_to ? formatDate(offer.valid_to) : "—"}</div>
                    </td>
                    <td className="table-actions">
                      <button className="ghost" onClick={() => handleEdit(offer)} type="button">
                        {t("actions.edit")}
                      </button>
                      <button
                        className="ghost"
                        onClick={() => handleSubmit(offer.id)}
                        type="button"
                        disabled={offer.status !== "DRAFT"}
                      >
                        {t("actions.submit")}
                      </button>
                      <button className="ghost" onClick={() => handleArchive(offer.id)} type="button">
                        {t("actions.archive")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <header className="section-header">
          <div>
            <h3>{editing ? t("marketplace.offers.form.editTitle") : t("marketplace.offers.form.createTitle")}</h3>
            <p className="muted">{t("marketplace.offers.form.subtitle")}</p>
          </div>
        </header>

        <div className="form-grid">
          <label className={`field ${formErrors.subject_id ? "error" : ""}`}>
            <span>{t("marketplace.offers.form.subjectType")}</span>
            <select
              value={form.subject_type}
              onChange={(event) => setForm((prev) => ({ ...prev, subject_type: event.target.value as MarketplaceOfferSubjectType }))}
            >
              <option value="PRODUCT">PRODUCT</option>
              <option value="SERVICE">SERVICE</option>
            </select>
          </label>
          <label className={`field ${formErrors.subject_id ? "error" : ""}`}>
            <span>{t("marketplace.offers.form.subjectId")}</span>
            <input
              value={form.subject_id}
              onChange={(event) => setForm((prev) => ({ ...prev, subject_id: event.target.value }))}
              placeholder="UUID"
            />
          </label>
          <label className="field">
            <span>{t("marketplace.offers.form.titleOverride")}</span>
            <input
              value={form.title_override}
              onChange={(event) => setForm((prev) => ({ ...prev, title_override: event.target.value }))}
            />
          </label>
          <label className={`field ${formErrors.currency ? "error" : ""}`}>
            <span>{t("marketplace.offers.form.currency")}</span>
            <input value={form.currency} onChange={(event) => setForm((prev) => ({ ...prev, currency: event.target.value }))} />
          </label>
          <label className="field">
            <span>{t("marketplace.offers.form.priceModel")}</span>
            <select
              value={form.price_model}
              onChange={(event) => setForm((prev) => ({ ...prev, price_model: event.target.value as MarketplaceOfferPriceModel }))}
            >
              <option value="FIXED">FIXED</option>
              <option value="RANGE">RANGE</option>
              <option value="PER_UNIT">PER_UNIT</option>
              <option value="PER_SERVICE">PER_SERVICE</option>
            </select>
          </label>
          {form.price_model === "RANGE" ? (
            <label className={`field ${formErrors.price_range ? "error" : ""}`}>
              <span>{t("marketplace.offers.form.priceRange")}</span>
              <div className="inline-fields">
                <input
                  value={form.price_min}
                  onChange={(event) => setForm((prev) => ({ ...prev, price_min: event.target.value }))}
                  placeholder={t("marketplace.offers.form.priceMin")}
                />
                <input
                  value={form.price_max}
                  onChange={(event) => setForm((prev) => ({ ...prev, price_max: event.target.value }))}
                  placeholder={t("marketplace.offers.form.priceMax")}
                />
              </div>
            </label>
          ) : (
            <label className={`field ${formErrors.price_amount ? "error" : ""}`}>
              <span>{t("marketplace.offers.form.priceAmount")}</span>
              <input
                value={form.price_amount}
                onChange={(event) => setForm((prev) => ({ ...prev, price_amount: event.target.value }))}
              />
            </label>
          )}
          <label className="field">
            <span>{t("marketplace.offers.form.geoScope")}</span>
            <select
              value={form.geo_scope}
              onChange={(event) => setForm((prev) => ({ ...prev, geo_scope: event.target.value as MarketplaceOfferGeoScope }))}
            >
              <option value="ALL_PARTNER_LOCATIONS">ALL_PARTNER_LOCATIONS</option>
              <option value="SELECTED_LOCATIONS">SELECTED_LOCATIONS</option>
              <option value="REGION">REGION</option>
            </select>
          </label>
          {form.geo_scope === "SELECTED_LOCATIONS" ? (
            <label className={`field ${formErrors.location_ids ? "error" : ""}`}>
              <span>{t("marketplace.offers.form.locationIds")}</span>
              <input
                value={form.location_ids}
                onChange={(event) => setForm((prev) => ({ ...prev, location_ids: event.target.value }))}
                placeholder={t("marketplace.offers.form.commaSeparated")}
              />
            </label>
          ) : null}
          {form.geo_scope === "REGION" ? (
            <label className={`field ${formErrors.region_code ? "error" : ""}`}>
              <span>{t("marketplace.offers.form.regionCode")}</span>
              <input
                value={form.region_code}
                onChange={(event) => setForm((prev) => ({ ...prev, region_code: event.target.value }))}
              />
            </label>
          ) : null}
          <label className="field">
            <span>{t("marketplace.offers.form.entitlementScope")}</span>
            <select
              value={form.entitlement_scope}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, entitlement_scope: event.target.value as MarketplaceOfferEntitlementScope }))
              }
            >
              <option value="ALL_CLIENTS">ALL_CLIENTS</option>
              <option value="SUBSCRIPTION_ONLY">SUBSCRIPTION_ONLY</option>
              <option value="SEGMENT_ONLY">SEGMENT_ONLY</option>
            </select>
          </label>
          {form.entitlement_scope === "SUBSCRIPTION_ONLY" ? (
            <label className={`field ${formErrors.allowed_subscription_codes ? "error" : ""}`}>
              <span>{t("marketplace.offers.form.subscriptionCodes")}</span>
              <input
                value={form.allowed_subscription_codes}
                onChange={(event) => setForm((prev) => ({ ...prev, allowed_subscription_codes: event.target.value }))}
                placeholder={t("marketplace.offers.form.commaSeparated")}
              />
            </label>
          ) : null}
          {form.entitlement_scope === "SEGMENT_ONLY" ? (
            <label className={`field ${formErrors.allowed_client_ids ? "error" : ""}`}>
              <span>{t("marketplace.offers.form.clientIds")}</span>
              <input
                value={form.allowed_client_ids}
                onChange={(event) => setForm((prev) => ({ ...prev, allowed_client_ids: event.target.value }))}
                placeholder={t("marketplace.offers.form.commaSeparated")}
              />
            </label>
          ) : null}
          <label className="field">
            <span>{t("marketplace.offers.form.validFrom")}</span>
            <input
              type="datetime-local"
              value={form.valid_from}
              onChange={(event) => setForm((prev) => ({ ...prev, valid_from: event.target.value }))}
            />
          </label>
          <label className="field">
            <span>{t("marketplace.offers.form.validTo")}</span>
            <input
              type="datetime-local"
              value={form.valid_to}
              onChange={(event) => setForm((prev) => ({ ...prev, valid_to: event.target.value }))}
            />
          </label>
        </div>

        {actionError ? <div className="form-error">{actionError}</div> : null}

        <div className="form-actions">
          <button className="primary" onClick={handleSave} type="button">
            {editing ? t("actions.save") : t("actions.saveDraft")}
          </button>
          {editing ? (
            <button className="ghost" onClick={resetForm} type="button">
              {t("actions.cancel")}
            </button>
          ) : null}
        </div>
      </section>
    </div>
  );
}

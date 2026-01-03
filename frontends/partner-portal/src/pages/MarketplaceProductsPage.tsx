import { useEffect, useMemo, useState } from "react";
import {
  archiveMarketplaceProduct,
  createMarketplaceProduct,
  fetchMarketplaceProduct,
  fetchMarketplaceProducts,
  publishMarketplaceProduct,
  updateMarketplaceProduct,
} from "../api/marketplaceCatalog";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime, formatNumber } from "../utils/format";
import { useI18n } from "../i18n";
import type {
  MarketplacePriceConfig,
  MarketplacePriceModel,
  MarketplaceProduct,
  MarketplaceProductStatus,
  MarketplaceProductSummary,
  MarketplaceProductType,
} from "../types/marketplace";

const defaultFormState = {
  type: "SERVICE" as MarketplaceProductType,
  title: "",
  description: "",
  category: "",
  priceModel: "FIXED" as MarketplacePriceModel,
  fixedAmount: "",
  unit: "item" as "liter" | "item" | "hour",
  amountPerUnit: "",
  tiers: [{ from: "", to: "", amount: "" }],
};

type TierRow = { from: string; to: string; amount: string };

type FormState = typeof defaultFormState;

const buildPriceSummary = (product: MarketplaceProductSummary) => {
  if (product.price_model === "FIXED") {
    const amount = (product.price_config as { amount: number }).amount;
    return `${formatNumber(amount)} ₽`;
  }
  if (product.price_model === "PER_UNIT") {
    const config = product.price_config as { amount_per_unit: number; unit: string };
    return `${formatNumber(config.amount_per_unit)} ₽ / ${config.unit}`;
  }
  const tiers = (product.price_config as { tiers: Array<{ from: number; to?: number | null; amount: number }> }).tiers;
  const first = tiers?.[0];
  if (!first) return "—";
  return `${formatNumber(first.amount)} ₽`;
};

const mapProductToForm = (product: MarketplaceProduct): FormState => {
  const next = { ...defaultFormState };
  next.type = product.type;
  next.title = product.title;
  next.description = product.description;
  next.category = product.category;
  next.priceModel = product.price_model;
  if (product.price_model === "FIXED") {
    next.fixedAmount = String((product.price_config as { amount: number }).amount ?? "");
  }
  if (product.price_model === "PER_UNIT") {
    const config = product.price_config as { amount_per_unit: number; unit: "liter" | "item" | "hour" };
    next.unit = config.unit;
    next.amountPerUnit = String(config.amount_per_unit ?? "");
  }
  if (product.price_model === "TIERED") {
    const config = product.price_config as { tiers: Array<{ from: number; to?: number | null; amount: number }> };
    next.tiers = config.tiers.map((tier) => ({
      from: tier.from?.toString() ?? "",
      to: tier.to?.toString() ?? "",
      amount: tier.amount?.toString() ?? "",
    }));
  }
  return next;
};

const buildPriceConfig = (form: FormState): { config?: MarketplacePriceConfig; errors: Record<string, string> } => {
  const errors: Record<string, string> = {};
  if (form.priceModel === "FIXED") {
    if (!form.fixedAmount) {
      errors.fixedAmount = "required";
    }
    const amount = Number(form.fixedAmount);
    if (Number.isNaN(amount) || amount <= 0) {
      errors.fixedAmount = "invalid";
    }
    return { config: { amount, currency: "RUB" }, errors };
  }
  if (form.priceModel === "PER_UNIT") {
    if (!form.amountPerUnit) {
      errors.amountPerUnit = "required";
    }
    const amount = Number(form.amountPerUnit);
    if (Number.isNaN(amount) || amount <= 0) {
      errors.amountPerUnit = "invalid";
    }
    return { config: { unit: form.unit, amount_per_unit: amount, currency: "RUB" }, errors };
  }
  const tiers = form.tiers.map((tier, index) => {
    const from = Number(tier.from);
    const amount = Number(tier.amount);
    const to = tier.to ? Number(tier.to) : null;
    if (!tier.from || Number.isNaN(from)) {
      errors[`tier_from_${index}`] = "invalid";
    }
    if (!tier.amount || Number.isNaN(amount)) {
      errors[`tier_amount_${index}`] = "invalid";
    }
    if (tier.to && Number.isNaN(to)) {
      errors[`tier_to_${index}`] = "invalid";
    }
    return { from, to, amount };
  });
  if (!tiers.length) {
    errors.tiers = "required";
  }
  return { config: { currency: "RUB", tiers }, errors };
};

export function MarketplaceProductsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [items, setItems] = useState<MarketplaceProductSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<MarketplaceProductStatus | "">("");
  const [typeFilter, setTypeFilter] = useState<MarketplaceProductType | "">("");
  const [query, setQuery] = useState("");
  const [form, setForm] = useState<FormState>(defaultFormState);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<MarketplaceProduct | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      status: statusFilter || undefined,
      type: typeFilter || undefined,
      q: query || undefined,
    }),
    [statusFilter, typeFilter, query],
  );

  const loadProducts = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchMarketplaceProducts(user.token, filters)
      .then((data) => {
        setItems(data.items ?? []);
      })
      .catch(() => setError(t("marketplace.products.loadError")))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, filters.status, filters.type, filters.q]);

  const resetForm = () => {
    setEditing(null);
    setForm(defaultFormState);
    setFormErrors({});
  };

  const submitForm = async () => {
    if (!user) return;
    setActionError(null);
    const validation = buildPriceConfig(form);
    setFormErrors(validation.errors);
    if (Object.keys(validation.errors).length) {
      setActionError(t("marketplace.products.validationError"));
      return;
    }
    setIsSaving(true);
    try {
      if (editing) {
        await updateMarketplaceProduct(user.token, editing.id, {
          type: form.type,
          title: form.title.trim(),
          description: form.description.trim(),
          category: form.category.trim(),
          price_model: form.priceModel,
          price_config: validation.config!,
        });
      } else {
        await createMarketplaceProduct(user.token, {
          type: form.type,
          title: form.title.trim(),
          description: form.description.trim(),
          category: form.category.trim(),
          price_model: form.priceModel,
          price_config: validation.config!,
        });
      }
      resetForm();
      loadProducts();
    } catch (err) {
      console.error(err);
      setActionError(t("marketplace.products.saveError"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleEdit = (product: MarketplaceProductSummary) => {
    if (!user) return;
    setActionError(null);
    setIsSaving(true);
    fetchMarketplaceProduct(user.token, product.id)
      .then((detailed) => {
        setEditing(detailed);
        setForm(mapProductToForm(detailed));
      })
      .catch(() => setActionError(t("marketplace.products.loadError")))
      .finally(() => setIsSaving(false));
  };

  const handlePublish = async (product: MarketplaceProductSummary) => {
    if (!user) return;
    if (!window.confirm(t("marketplace.products.confirmPublish"))) return;
    setActionError(null);
    try {
      await publishMarketplaceProduct(user.token, product.id);
      loadProducts();
    } catch (err) {
      console.error(err);
      setActionError(t("marketplace.products.publishError"));
    }
  };

  const handleArchive = async (product: MarketplaceProductSummary) => {
    if (!user) return;
    if (!window.confirm(t("marketplace.products.confirmArchive"))) return;
    setActionError(null);
    try {
      await archiveMarketplaceProduct(user.token, product.id);
      loadProducts();
    } catch (err) {
      console.error(err);
      setActionError(t("marketplace.products.archiveError"));
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("marketplace.products.title")}</h2>
            <p className="muted">{t("marketplace.products.subtitle")}</p>
          </div>
          <button className="ghost" type="button" onClick={loadProducts}>
            {t("actions.refresh")}
          </button>
        </div>
        <div className="filters">
          <label>
            <span className="label">{t("marketplace.products.filters.status")}</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as MarketplaceProductStatus | "")}>
              <option value="">{t("common.all")}</option>
              <option value="DRAFT">{t("marketplace.products.statuses.DRAFT")}</option>
              <option value="PUBLISHED">{t("marketplace.products.statuses.PUBLISHED")}</option>
              <option value="ARCHIVED">{t("marketplace.products.statuses.ARCHIVED")}</option>
            </select>
          </label>
          <label>
            <span className="label">{t("marketplace.products.filters.type")}</span>
            <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as MarketplaceProductType | "")}>
              <option value="">{t("common.all")}</option>
              <option value="SERVICE">{t("marketplace.products.types.SERVICE")}</option>
              <option value="PRODUCT">{t("marketplace.products.types.PRODUCT")}</option>
            </select>
          </label>
          <label>
            <span className="label">{t("marketplace.products.filters.search")}</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("marketplace.products.filters.searchPlaceholder")} />
          </label>
        </div>
        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <div className="error" role="alert">{error}</div>
        ) : items.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("marketplace.products.table.title")}</th>
                <th>{t("marketplace.products.table.type")}</th>
                <th>{t("marketplace.products.table.category")}</th>
                <th>{t("common.status")}</th>
                <th>{t("marketplace.products.table.price")}</th>
                <th>{t("marketplace.products.table.updated")}</th>
                <th>{t("common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((product) => (
                <tr key={product.id}>
                  <td>{product.title}</td>
                  <td>{t(`marketplace.products.types.${product.type}`)}</td>
                  <td>{product.category}</td>
                  <td><StatusBadge status={product.status} /></td>
                  <td>{buildPriceSummary(product)}</td>
                  <td>{formatDateTime(product.updated_at ?? product.published_at ?? null)}</td>
                  <td>
                    <div className="table-actions">
                      <button className="link-button" type="button" onClick={() => handleEdit(product)}>
                        {t("actions.edit")}
                      </button>
                      <button
                        className="link-button"
                        type="button"
                        onClick={() => handlePublish(product)}
                        disabled={product.status !== "DRAFT"}
                      >
                        {t("actions.publish")}
                      </button>
                      <button
                        className="link-button danger"
                        type="button"
                        onClick={() => handleArchive(product)}
                        disabled={product.status === "ARCHIVED"}
                      >
                        {t("marketplace.products.actions.archive")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">
            <h3>{t("marketplace.products.emptyTitle")}</h3>
            <p>{t("marketplace.products.emptyDescription")}</p>
          </div>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>{editing ? t("marketplace.products.editTitle") : t("marketplace.products.createTitle")}</h3>
          {editing ? (
            <button className="ghost" type="button" onClick={resetForm}>
              {t("marketplace.products.cancelEdit")}
            </button>
          ) : null}
        </div>
        <div className="form-grid">
          <label className="form-field">
            <span className="label">{t("marketplace.products.fields.type")}</span>
            <select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value as MarketplaceProductType })}>
              <option value="SERVICE">{t("marketplace.products.types.SERVICE")}</option>
              <option value="PRODUCT">{t("marketplace.products.types.PRODUCT")}</option>
            </select>
          </label>
          <label className="form-field">
            <span className="label">{t("marketplace.products.fields.title")}</span>
            <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          </label>
          <label className="form-field">
            <span className="label">{t("marketplace.products.fields.category")}</span>
            <input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} />
          </label>
          <label className="form-field form-grid__full">
            <span className="label">{t("marketplace.products.fields.description")}</span>
            <textarea rows={3} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          </label>
        </div>
        <div className="form-grid">
          <label className="form-field">
            <span className="label">{t("marketplace.products.fields.priceModel")}</span>
            <select value={form.priceModel} onChange={(event) => setForm({ ...defaultFormState, ...form, priceModel: event.target.value as MarketplacePriceModel })}>
              <option value="FIXED">{t("marketplace.products.priceModels.FIXED")}</option>
              <option value="PER_UNIT">{t("marketplace.products.priceModels.PER_UNIT")}</option>
              <option value="TIERED">{t("marketplace.products.priceModels.TIERED")}</option>
            </select>
          </label>
          {form.priceModel === "FIXED" ? (
            <label className="form-field">
              <span className="label">{t("marketplace.products.fields.amount")}</span>
              <input
                type="number"
                value={form.fixedAmount}
                onChange={(event) => setForm({ ...form, fixedAmount: event.target.value })}
              />
              {formErrors.fixedAmount ? <span className="error-text">{t("marketplace.products.validation.amount")}</span> : null}
            </label>
          ) : null}
          {form.priceModel === "PER_UNIT" ? (
            <>
              <label className="form-field">
                <span className="label">{t("marketplace.products.fields.unit")}</span>
                <select value={form.unit} onChange={(event) => setForm({ ...form, unit: event.target.value as "liter" | "item" | "hour" })}>
                  <option value="item">{t("marketplace.products.units.item")}</option>
                  <option value="liter">{t("marketplace.products.units.liter")}</option>
                  <option value="hour">{t("marketplace.products.units.hour")}</option>
                </select>
              </label>
              <label className="form-field">
                <span className="label">{t("marketplace.products.fields.amountPerUnit")}</span>
                <input
                  type="number"
                  value={form.amountPerUnit}
                  onChange={(event) => setForm({ ...form, amountPerUnit: event.target.value })}
                />
                {formErrors.amountPerUnit ? <span className="error-text">{t("marketplace.products.validation.amount")}</span> : null}
              </label>
            </>
          ) : null}
        </div>
        {form.priceModel === "TIERED" ? (
          <div className="stack">
            <div className="section-title">
              <h4>{t("marketplace.products.fields.tiers")}</h4>
              <button
                className="ghost"
                type="button"
                onClick={() => setForm({ ...form, tiers: [...form.tiers, { from: "", to: "", amount: "" }] })}
              >
                {t("marketplace.products.actions.addTier")}
              </button>
            </div>
            {form.tiers.map((tier: TierRow, index: number) => (
              <div className="form-grid" key={`tier-${index}`}>
                <label className="form-field">
                  <span className="label">{t("marketplace.products.fields.tierFrom")}</span>
                  <input
                    type="number"
                    value={tier.from}
                    onChange={(event) => {
                      const next = [...form.tiers];
                      next[index] = { ...next[index], from: event.target.value };
                      setForm({ ...form, tiers: next });
                    }}
                  />
                </label>
                <label className="form-field">
                  <span className="label">{t("marketplace.products.fields.tierTo")}</span>
                  <input
                    type="number"
                    value={tier.to}
                    onChange={(event) => {
                      const next = [...form.tiers];
                      next[index] = { ...next[index], to: event.target.value };
                      setForm({ ...form, tiers: next });
                    }}
                  />
                </label>
                <label className="form-field">
                  <span className="label">{t("marketplace.products.fields.tierAmount")}</span>
                  <input
                    type="number"
                    value={tier.amount}
                    onChange={(event) => {
                      const next = [...form.tiers];
                      next[index] = { ...next[index], amount: event.target.value };
                      setForm({ ...form, tiers: next });
                    }}
                  />
                </label>
                <div className="form-grid__actions">
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => {
                      const next = form.tiers.filter((_, idx) => idx !== index);
                      setForm({ ...form, tiers: next.length ? next : [{ from: "", to: "", amount: "" }] });
                    }}
                  >
                    {t("actions.delete")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : null}
        {actionError ? <div className="error" role="alert">{actionError}</div> : null}
        <div className="actions">
          <button
            className="primary"
            type="button"
            onClick={submitForm}
            disabled={isSaving || !form.title.trim() || !form.category.trim()}
          >
            {editing ? t("marketplace.products.actions.saveChanges") : t("marketplace.products.actions.createDraft")}
          </button>
        </div>
      </section>
    </div>
  );
}

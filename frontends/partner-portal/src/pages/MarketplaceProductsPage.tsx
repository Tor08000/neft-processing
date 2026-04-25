import { useEffect, useMemo, useRef, useState } from "react";
import {
  addMarketplaceProductMedia,
  archiveMarketplaceProduct,
  createMarketplaceProduct,
  fetchMarketplaceProduct,
  fetchMarketplaceProducts,
  removeMarketplaceProductMedia,
  submitMarketplaceProduct,
  updateMarketplaceProduct,
} from "../api/marketplaceCatalog";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";
import { useTranslation } from "react-i18next";
import { EmptyState } from "@shared/ui/EmptyState";
import { PartnerErrorState } from "../components/PartnerErrorState";
import type {
  MarketplaceProduct,
  MarketplaceProductMedia,
  MarketplaceProductStatus,
  MarketplaceProductSummary,
} from "../types/marketplace";

const defaultFormState = {
  title: "",
  description: "",
  category: "",
  tags: [] as string[],
  attributes: [{ key: "", value: "" }],
  variants: [{ name: "", sku: "", props: "" }],
};

type Primitive = string | number | boolean | null;

export type ProductVariant = {
  name: string;
  sku: string;
  props: Record<string, Primitive>;
};

type AttributeRow = { key: string; value: string };
type VariantRow = { name: string; sku: string; props: string };
type FormState = typeof defaultFormState;

function normalizeVariant(input: any): ProductVariant {
  let props: Record<string, Primitive> = {};

  if (input?.props && typeof input.props === "object" && !Array.isArray(input.props)) {
    props = input.props as Record<string, Primitive>;
  } else if (typeof input?.props === "string") {
    try {
      const parsed = JSON.parse(input.props);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        props = parsed as Record<string, Primitive>;
      }
    } catch {
      props = {};
    }
  }

  return {
    name: String(input?.name ?? ""),
    sku: String(input?.sku ?? ""),
    props,
  };
}

const buildAttributes = (rows: AttributeRow[]) =>
  rows.reduce<Record<string, string | number | boolean | null>>((acc, row) => {
    if (row.key.trim()) {
      acc[row.key.trim()] = row.value.trim();
    }
    return acc;
  }, {});

const buildVariants = (
  rows: VariantRow[],
): { variants: ProductVariant[]; errors: Record<string, string> } => {
  const errors: Record<string, string> = {};
  const variants = rows
    .filter((row) => row.name.trim() || row.sku.trim() || row.props.trim())
    .map((row, index) => {
      const propsValue = row.props.trim();
      if (!propsValue) {
        return normalizeVariant({ name: row.name.trim(), sku: row.sku.trim(), props: {} });
      }
      try {
        const parsed = JSON.parse(propsValue);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          errors[`variant_props_${index}`] = "invalid";
          return normalizeVariant({ name: row.name.trim(), sku: row.sku.trim(), props: {} });
        }
        return normalizeVariant({ name: row.name.trim(), sku: row.sku.trim(), props: parsed });
      } catch {
        errors[`variant_props_${index}`] = "invalid";
        return normalizeVariant({ name: row.name.trim(), sku: row.sku.trim(), props: {} });
      }
    });
  return { variants, errors };
};

const mapProductToForm = (product: MarketplaceProduct): FormState => {
  const attributes = Object.entries(product.attributes ?? {}).map(([key, value]) => ({
    key,
    value: String(value ?? ""),
  }));
  const variants = (product.variants ?? []).map((variant) => {
    const normalized = normalizeVariant(variant);
    return {
      name: normalized.name,
      sku: normalized.sku,
      props: JSON.stringify(normalized.props ?? {}, null, 2),
    };
  });
  return {
    title: product.title,
    description: product.description ?? "",
    category: product.category,
    tags: product.tags ?? [],
    attributes: attributes.length ? attributes : [{ key: "", value: "" }],
    variants: variants.length ? variants : [{ name: "", sku: "", props: "" }],
  };
};

const createAttachmentId = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `attachment-${Math.random().toString(16).slice(2)}`;
};

export function MarketplaceProductsPage() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [items, setItems] = useState<MarketplaceProductSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [statusFilter, setStatusFilter] = useState<MarketplaceProductStatus | "">("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [query, setQuery] = useState("");
  const [form, setForm] = useState<FormState>(defaultFormState);
  const [tagInput, setTagInput] = useState("");
  const [mediaItems, setMediaItems] = useState<MarketplaceProductMedia[]>([]);
  const [mediaUrl, setMediaUrl] = useState("");
  const [mediaMime, setMediaMime] = useState("image/jpeg");
  const [mediaSort, setMediaSort] = useState("0");
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<MarketplaceProduct | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const formRef = useRef<HTMLDivElement | null>(null);

  const filters = useMemo(
    () => ({
      status: statusFilter || undefined,
      category: categoryFilter || undefined,
      q: query || undefined,
    }),
    [statusFilter, categoryFilter, query],
  );

  const loadProducts = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchMarketplaceProducts(user.token, filters)
      .then((data) => {
        setItems(data.items ?? []);
      })
      .catch((err) => {
        setError(err);
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, filters.status, filters.category, filters.q]);

  const resetForm = () => {
    setEditing(null);
    setForm(defaultFormState);
    setTagInput("");
    setMediaItems([]);
    setMediaUrl("");
    setMediaMime("image/jpeg");
    setMediaSort("0");
    setFormErrors({});
  };

  const submitForm = async () => {
    if (!user) return;
    setActionError(null);
    const errors: Record<string, string> = {};
    if (!form.title.trim()) errors.title = "required";
    if (!form.category.trim()) errors.category = "required";
    const { variants, errors: variantErrors } = buildVariants(form.variants);
    Object.assign(errors, variantErrors);
    setFormErrors(errors);
    if (Object.keys(errors).length) {
      setActionError(t("marketplace.products.validationError"));
      return;
    }
    setIsSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim(),
        category: form.category.trim(),
        tags: form.tags,
        attributes: buildAttributes(form.attributes),
        variants,
      };
      if (editing) {
        await updateMarketplaceProduct(user.token, editing.id, payload);
      } else {
        await createMarketplaceProduct(user.token, payload);
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
        const media = detailed.media ?? [];
        setMediaItems(media);
        setMediaSort(String(media.length));
      })
      .catch(() => setActionError(t("marketplace.products.loadError")))
      .finally(() => setIsSaving(false));
  };

  const handleSubmit = async (product: MarketplaceProductSummary) => {
    if (!user) return;
    if (!window.confirm(t("marketplace.products.confirmSubmit"))) return;
    setActionError(null);
    try {
      await submitMarketplaceProduct(user.token, product.id);
      loadProducts();
    } catch (err) {
      console.error(err);
      setActionError(t("marketplace.products.submitError"));
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

  const handleAddTag = () => {
    const nextTag = tagInput.trim();
    if (!nextTag) return;
    if (!form.tags.includes(nextTag)) {
      setForm({ ...form, tags: [...form.tags, nextTag] });
    }
    setTagInput("");
  };

  const handleRemoveTag = (tag: string) => {
    setForm({ ...form, tags: form.tags.filter((item) => item !== tag) });
  };

  const handleAddMedia = async () => {
    if (!user || !editing) return;
    if (!mediaUrl.trim()) {
      setActionError(t("marketplace.products.validationError"));
      return;
    }
    setActionError(null);
    setIsSaving(true);
    try {
      const attachment_id = createAttachmentId();
      const payload: MarketplaceProductMedia = {
        attachment_id,
        bucket: "external",
        path: mediaUrl.trim(),
        mime: mediaMime.trim() || "image/jpeg",
        sort_index: Number(mediaSort) || mediaItems.length,
      };
      const response = await addMarketplaceProductMedia(user.token, editing.id, payload);
      setMediaItems((prev) => [...prev, response].sort((a, b) => (a.sort_index ?? 0) - (b.sort_index ?? 0)));
      setMediaUrl("");
      setMediaSort(String(mediaItems.length + 1));
    } catch (err) {
      console.error(err);
      setActionError(t("marketplace.products.saveError"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemoveMedia = async (media: MarketplaceProductMedia) => {
    if (!user || !editing) return;
    setActionError(null);
    setIsSaving(true);
    try {
      await removeMarketplaceProductMedia(user.token, editing.id, media.attachment_id);
      setMediaItems((prev) => prev.filter((item) => item.attachment_id !== media.attachment_id));
    } catch (err) {
      console.error(err);
      setActionError(t("marketplace.products.archiveError"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleMoveMedia = async (media: MarketplaceProductMedia, direction: -1 | 1) => {
    if (!user || !editing) return;
    const index = mediaItems.findIndex((item) => item.attachment_id === media.attachment_id);
    const swapIndex = index + direction;
    if (index < 0 || swapIndex < 0 || swapIndex >= mediaItems.length) return;
    const nextItems = [...mediaItems];
    const temp = nextItems[index];
    nextItems[index] = nextItems[swapIndex];
    nextItems[swapIndex] = temp;
    const reordered = nextItems.map((item, idx) => ({ ...item, sort_index: idx }));
    setMediaItems(reordered);
    setIsSaving(true);
    try {
      await Promise.all(
        [reordered[index], reordered[swapIndex]].map((item) =>
          addMarketplaceProductMedia(user.token, editing.id, {
            attachment_id: item.attachment_id,
            bucket: item.bucket,
            path: item.path,
            checksum: item.checksum ?? undefined,
            size: item.size ?? undefined,
            mime: item.mime ?? undefined,
            sort_index: item.sort_index ?? 0,
          }),
        ),
      );
    } catch (err) {
      console.error(err);
      setActionError(t("marketplace.products.saveError"));
    } finally {
      setIsSaving(false);
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
          <div className="neft-actions">
            <button className="ghost" type="button" onClick={loadProducts}>
              {t("actions.refresh")}
            </button>
          </div>
        </div>
        <div className="filters neft-filters">
          <label className="filter neft-filter">
            <span className="label">{t("marketplace.products.filters.status")}</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as MarketplaceProductStatus | "")}>
              <option value="">{t("common.all")}</option>
              <option value="DRAFT">{t("marketplace.products.statuses.DRAFT")}</option>
              <option value="PENDING_REVIEW">{t("marketplace.products.statuses.PENDING_REVIEW")}</option>
              <option value="ACTIVE">{t("marketplace.products.statuses.ACTIVE")}</option>
              <option value="SUSPENDED">{t("marketplace.products.statuses.SUSPENDED")}</option>
              <option value="ARCHIVED">{t("marketplace.products.statuses.ARCHIVED")}</option>
            </select>
          </label>
          <label className="filter neft-filter">
            <span className="label">{t("marketplace.products.filters.category")}</span>
            <input value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)} />
          </label>
          <label className="filter neft-filter">
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
          <PartnerErrorState error={error} />
        ) : items.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("marketplace.products.table.title")}</th>
                <th>{t("marketplace.products.table.category")}</th>
                <th>{t("marketplace.products.table.status")}</th>
                <th>{t("marketplace.products.table.updated")}</th>
                <th>{t("common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((product) => (
                <tr key={product.id}>
                  <td>{product.title}</td>
                  <td>{product.category}</td>
                  <td><StatusBadge status={product.status} /></td>
                  <td>{formatDateTime(product.updated_at ?? product.created_at ?? null)}</td>
                  <td>
                    <div className="table-actions">
                      <button className="link-button" type="button" onClick={() => handleEdit(product)}>
                        {t("actions.edit")}
                      </button>
                      <button
                        className="link-button"
                        type="button"
                        onClick={() => handleSubmit(product)}
                        disabled={product.status !== "DRAFT"}
                      >
                        {t("marketplace.products.actions.submit")}
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
          <EmptyState
            title={t("marketplace.products.emptyTitle")}
            description={t("marketplace.products.emptyDescription")}
            hint="Добавьте первую позицию через форму ниже."
            primaryAction={{
              label: "Создать позицию",
              onClick: () => formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
            }}
            secondaryAction={{ label: t("actions.refresh"), onClick: loadProducts }}
          />
        )}
      </section>

      <section className="card" ref={formRef}>
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
            <span className="label">{t("marketplace.products.fields.title")}</span>
            <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
            {formErrors.title ? <span className="error-text">{t("marketplace.products.validation.required")}</span> : null}
          </label>
          <label className="form-field">
            <span className="label">{t("marketplace.products.fields.category")}</span>
            <input value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} />
            {formErrors.category ? <span className="error-text">{t("marketplace.products.validation.required")}</span> : null}
          </label>
          <label className="form-field form-grid__full">
            <span className="label">{t("marketplace.products.fields.description")}</span>
            <textarea rows={3} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          </label>
        </div>
        <div className="stack">
          <div className="section-title">
            <h4>{t("marketplace.products.fields.tags")}</h4>
          </div>
          <div className="tag-input">
            <input
              value={tagInput}
              onChange={(event) => setTagInput(event.target.value)}
              placeholder={t("marketplace.products.fields.tags")}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  handleAddTag();
                }
              }}
            />
            <button className="ghost" type="button" onClick={handleAddTag}>
              {t("marketplace.products.actions.addTag")}
            </button>
          </div>
          {form.tags.length ? (
            <div className="tag-list">
              {form.tags.map((tag) => (
                <button className="tag" type="button" key={tag} onClick={() => handleRemoveTag(tag)}>
                  {tag} ×
                </button>
              ))}
            </div>
          ) : null}
        </div>
        <div className="stack">
          <div className="section-title">
            <h4>{t("marketplace.products.fields.attributes")}</h4>
            <button
              className="ghost"
              type="button"
              onClick={() => setForm({ ...form, attributes: [...form.attributes, { key: "", value: "" }] })}
            >
              {t("marketplace.products.actions.addAttribute")}
            </button>
          </div>
          {form.attributes.map((attribute, index) => (
            <div className="form-grid" key={`attribute-${index}`}>
              <label className="form-field">
                <span className="label">{t("marketplace.products.fields.attributeKey")}</span>
                <input
                  value={attribute.key}
                  onChange={(event) => {
                    const next = [...form.attributes];
                    next[index] = { ...next[index], key: event.target.value };
                    setForm({ ...form, attributes: next });
                  }}
                />
              </label>
              <label className="form-field">
                <span className="label">{t("marketplace.products.fields.attributeValue")}</span>
                <input
                  value={attribute.value}
                  onChange={(event) => {
                    const next = [...form.attributes];
                    next[index] = { ...next[index], value: event.target.value };
                    setForm({ ...form, attributes: next });
                  }}
                />
              </label>
              <div className="form-grid__actions">
                <button
                  className="ghost"
                  type="button"
                  onClick={() => {
                    const next = form.attributes.filter((_, idx) => idx !== index);
                    setForm({ ...form, attributes: next.length ? next : [{ key: "", value: "" }] });
                  }}
                >
                  {t("actions.delete")}
                </button>
              </div>
            </div>
          ))}
        </div>
        <div className="stack">
          <div className="section-title">
            <h4>{t("marketplace.products.fields.variants")}</h4>
            <button
              className="ghost"
              type="button"
              onClick={() => setForm({ ...form, variants: [...form.variants, { name: "", sku: "", props: "" }] })}
            >
              {t("marketplace.products.actions.addVariant")}
            </button>
          </div>
          {form.variants.map((variant, index) => (
            <div className="form-grid" key={`variant-${index}`}>
              <label className="form-field">
                <span className="label">{t("marketplace.products.fields.variantName")}</span>
                <input
                  value={variant.name}
                  onChange={(event) => {
                    const next = [...form.variants];
                    next[index] = { ...next[index], name: event.target.value };
                    setForm({ ...form, variants: next });
                  }}
                />
              </label>
              <label className="form-field">
                <span className="label">{t("marketplace.products.fields.variantSku")}</span>
                <input
                  value={variant.sku}
                  onChange={(event) => {
                    const next = [...form.variants];
                    next[index] = { ...next[index], sku: event.target.value };
                    setForm({ ...form, variants: next });
                  }}
                />
              </label>
              <label className="form-field form-grid__full">
                <span className="label">{t("marketplace.products.fields.variantProps")}</span>
                <textarea
                  rows={2}
                  value={variant.props}
                  onChange={(event) => {
                    const next = [...form.variants];
                    next[index] = { ...next[index], props: event.target.value };
                    setForm({ ...form, variants: next });
                  }}
                />
                {formErrors[`variant_props_${index}`] ? (
                  <span className="error-text">{t("marketplace.products.validation.invalidJson")}</span>
                ) : null}
              </label>
              <div className="form-grid__actions">
                <button
                  className="ghost"
                  type="button"
                  onClick={() => {
                    const next = form.variants.filter((_, idx) => idx !== index);
                    setForm({ ...form, variants: next.length ? next : [{ name: "", sku: "", props: "" }] });
                  }}
                >
                  {t("actions.delete")}
                </button>
              </div>
            </div>
          ))}
        </div>
        <div className="stack">
          <div className="section-title">
            <h4>{t("marketplace.products.fields.media")}</h4>
          </div>
          {editing ? (
            <>
              <div className="form-grid">
                <label className="form-field form-grid__full">
                  <span className="label">{t("marketplace.products.fields.mediaUrl")}</span>
                  <input value={mediaUrl} onChange={(event) => setMediaUrl(event.target.value)} />
                </label>
                <label className="form-field">
                  <span className="label">{t("marketplace.products.fields.mediaMime")}</span>
                  <input value={mediaMime} onChange={(event) => setMediaMime(event.target.value)} />
                </label>
                <label className="form-field">
                  <span className="label">{t("marketplace.products.fields.mediaSort")}</span>
                  <input value={mediaSort} onChange={(event) => setMediaSort(event.target.value)} />
                </label>
                <div className="form-grid__actions">
                  <button className="ghost" type="button" onClick={handleAddMedia} disabled={isSaving}>
                    {t("marketplace.products.actions.addMedia")}
                  </button>
                </div>
              </div>
              {mediaItems.length ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("marketplace.products.fields.mediaUrl")}</th>
                      <th>{t("marketplace.products.fields.mediaMime")}</th>
                      <th>{t("marketplace.products.fields.mediaSort")}</th>
                      <th>{t("common.actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mediaItems.map((media, index) => (
                      <tr key={media.attachment_id}>
                        <td>{media.path}</td>
                        <td>{media.mime}</td>
                        <td>{media.sort_index ?? index}</td>
                        <td>
                          <div className="table-actions">
                            <button className="link-button" type="button" onClick={() => handleMoveMedia(media, -1)}>
                              ↑
                            </button>
                            <button className="link-button" type="button" onClick={() => handleMoveMedia(media, 1)}>
                              ↓
                            </button>
                            <button className="link-button danger" type="button" onClick={() => handleRemoveMedia(media)}>
                              {t("actions.delete")}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </>
          ) : (
            <div className="muted">Сохраните карточку, чтобы добавить медиа.</div>
          )}
        </div>
        {actionError ? <div className="error" role="alert">{actionError}</div> : null}
        <div className="actions">
          <button
            className="primary"
            type="button"
            onClick={submitForm}
            disabled={isSaving || !form.title.trim() || !form.category.trim() || editing?.status === "ARCHIVED"}
          >
            {editing ? t("marketplace.products.actions.saveChanges") : t("marketplace.products.actions.createDraft")}
          </button>
        </div>
      </section>
    </div>
  );
}

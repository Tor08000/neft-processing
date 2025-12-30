import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  activateCatalogItem,
  fetchCatalogItem,
  updateCatalogItem,
  disableCatalogItem,
} from "../api/catalog";
import { activateOffer, createOffer, disableOffer, fetchOffers, updateOffer } from "../api/offers";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate, formatDateTime } from "../utils/format";
import { canManageServices, canReadServices } from "../utils/roles";
import type {
  CatalogItem,
  CatalogItemInput,
  CatalogItemKind,
  CatalogItemStatus,
  Offer,
  OfferAvailability,
  OfferInput,
  OfferLocationScope,
} from "../types/marketplace";

type ApiErrorState = {
  message: string;
  status?: number;
  correlationId?: string | null;
};

type CatalogFormState = {
  title: string;
  description: string;
  kind: CatalogItemKind;
  category: string;
  baseUom: string;
  status: CatalogItemStatus;
};

type OfferFormState = {
  price: string;
  currency: string;
  vatRate: string;
  validFrom: string;
  validTo: string;
  locationScope: OfferLocationScope;
  locationIds: string;
  availability: OfferAvailability;
  active: boolean;
};

const normalizeError = (error: unknown, fallback: string): ApiErrorState => {
  if (error instanceof ApiError) {
    return { message: error.message, status: error.status, correlationId: error.correlationId };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return { message: fallback };
};

const formatErrorDescription = (error: ApiErrorState): string => {
  if (error.status) {
    return `${error.message} (HTTP ${error.status})`;
  }
  return error.message;
};

const resolveCatalogTone = (status: CatalogItemStatus): "success" | "pending" | "error" | "neutral" => {
  switch (status) {
    case "ACTIVE":
      return "success";
    case "DISABLED":
      return "pending";
    case "ARCHIVED":
      return "error";
    case "DRAFT":
    default:
      return "neutral";
  }
};

const resolveOfferTone = (active: boolean): "success" | "pending" => (active ? "success" : "pending");

const formatOfferPrice = (value: number, currency: string): string =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency }).format(value);

const buildCatalogPayload = (form: CatalogFormState): CatalogItemInput => ({
  title: form.title.trim(),
  description: form.description.trim() || null,
  kind: form.kind,
  category: form.category.trim() || null,
  baseUom: form.baseUom.trim(),
  status: form.status,
});

const buildCatalogForm = (item: CatalogItem): CatalogFormState => ({
  title: item.title,
  description: item.description ?? "",
  kind: item.kind,
  category: item.category ?? "",
  baseUom: item.baseUom ?? "",
  status: item.status,
});

const buildOfferForm = (offer?: Offer | null): OfferFormState => ({
  price: offer?.price ? String(offer.price) : "",
  currency: offer?.currency ?? "RUB",
  vatRate: offer?.vatRate !== null && offer?.vatRate !== undefined ? String(offer.vatRate) : "",
  validFrom: offer?.validFrom ?? "",
  validTo: offer?.validTo ?? "",
  locationScope: offer?.locationScope ?? "all",
  locationIds: offer?.locationIds?.join(", ") ?? "",
  availability: offer?.availability ?? "always",
  active: offer?.active ?? false,
});

const buildOfferPayload = (catalogItemId: string, form: OfferFormState, activate: boolean): OfferInput => ({
  catalogItemId,
  price: Number(form.price),
  currency: form.currency,
  vatRate: form.vatRate ? Number(form.vatRate) : null,
  validFrom: form.validFrom || null,
  validTo: form.validTo || null,
  locationScope: form.locationScope,
  locationIds:
    form.locationScope === "selected"
      ? form.locationIds
          .split(",")
          .map((id) => id.trim())
          .filter(Boolean)
      : [],
  availability: form.availability,
  active: activate ? true : form.active,
});

const isOfferValidOnDate = (offer: Offer, dateFilter: string): boolean => {
  if (!dateFilter) return true;
  const date = new Date(dateFilter);
  if (Number.isNaN(date.getTime())) return true;
  const from = offer.validFrom ? new Date(offer.validFrom) : null;
  const to = offer.validTo ? new Date(offer.validTo) : null;
  if (from && date < from) return false;
  if (to && date > to) return false;
  return true;
};

export function ServiceDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();
  const canRead = canReadServices(user?.roles);
  const canManage = canManageServices(user?.roles);
  const [item, setItem] = useState<CatalogItem | null>(null);
  const [itemLoading, setItemLoading] = useState(true);
  const [itemError, setItemError] = useState<ApiErrorState | null>(null);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [offersLoading, setOffersLoading] = useState(true);
  const [offersError, setOffersError] = useState<ApiErrorState | null>(null);
  const [filters, setFilters] = useState({
    scope: "all",
    locationId: "",
    activeOnly: false,
    date: "",
  });
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionCorrelation, setActionCorrelation] = useState<string | null>(null);
  const [itemModalOpen, setItemModalOpen] = useState(false);
  const [itemForm, setItemForm] = useState<CatalogFormState | null>(null);
  const [itemFormError, setItemFormError] = useState<ApiErrorState | null>(null);
  const [offerModalOpen, setOfferModalOpen] = useState(false);
  const [editingOffer, setEditingOffer] = useState<Offer | null>(null);
  const [offerForm, setOfferForm] = useState<OfferFormState>(buildOfferForm());
  const [offerFormError, setOfferFormError] = useState<ApiErrorState | null>(null);

  useEffect(() => {
    if (!user || !id || !canRead) return;
    setItemLoading(true);
    setItemError(null);
    fetchCatalogItem(user.token, id)
      .then((data) => {
        setItem(data);
      })
      .catch((err) => setItemError(normalizeError(err, "Не удалось загрузить карточку услуги")))
      .finally(() => setItemLoading(false));
  }, [user, id, canRead]);

  const fetchItemOffers = async () => {
    if (!user || !id) return;
    setOffersLoading(true);
    setOffersError(null);
    try {
      const response = await fetchOffers(user.token, {
        catalog_item_id: id,
        active: filters.activeOnly ? "true" : undefined,
        location_id: filters.scope === "selected" ? filters.locationId || undefined : undefined,
      });
      setOffers(response.items ?? []);
    } catch (err) {
      setOffersError(normalizeError(err, "Не удалось загрузить офферы"));
    } finally {
      setOffersLoading(false);
    }
  };

  useEffect(() => {
    if (!user || !id || !canRead) return;
    fetchItemOffers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, id, canRead, filters.scope, filters.locationId, filters.activeOnly]);

  const filteredOffers = useMemo(
    () => offers.filter((offer) => isOfferValidOnDate(offer, filters.date)),
    [offers, filters.date],
  );

  if (!canRead) {
    return <ForbiddenState />;
  }

  const openItemModal = () => {
    if (!item) return;
    setItemForm(buildCatalogForm(item));
    setItemFormError(null);
    setItemModalOpen(true);
  };

  const handleSaveItem = async (activate = false) => {
    if (!user || !item || !itemForm) return;
    if (!itemForm.title.trim() || !itemForm.baseUom.trim()) {
      setItemFormError({ message: "Заполните обязательные поля" });
      return;
    }
    setItemFormError(null);
    setActionNotice(null);
    setActionCorrelation(null);
    try {
      const payload = buildCatalogPayload({ ...itemForm, status: activate ? "ACTIVE" : itemForm.status });
      const result = await updateCatalogItem(user.token, item.id, payload);
      setItem(result.data);
      setActionNotice("Карточка услуги обновлена");
      setActionCorrelation(result.correlationId ?? null);
      setItemModalOpen(false);
    } catch (err) {
      setItemFormError(normalizeError(err, "Не удалось сохранить изменения"));
    }
  };

  const handleToggleItem = async () => {
    if (!user || !item) return;
    setActionNotice(null);
    setActionCorrelation(null);
    try {
      if (item.status === "ACTIVE") {
        const result = await disableCatalogItem(user.token, item.id);
        setItem({ ...item, status: "DISABLED" });
        setActionNotice("Элемент отключён");
        setActionCorrelation(result.correlationId ?? null);
      } else {
        const result = await activateCatalogItem(user.token, item.id);
        setItem({ ...item, status: "ACTIVE" });
        setActionNotice("Элемент активирован");
        setActionCorrelation(result.correlationId ?? null);
      }
    } catch (err) {
      setItemError(normalizeError(err, "Не удалось изменить статус"));
    }
  };

  const openOfferModal = (offer?: Offer) => {
    setEditingOffer(offer ?? null);
    setOfferForm(buildOfferForm(offer));
    setOfferFormError(null);
    setOfferModalOpen(true);
  };

  const handleSaveOffer = async (activate = false) => {
    if (!user || !id) return;
    if (!offerForm.price) {
      setOfferFormError({ message: "Укажите цену" });
      return;
    }
    setOfferFormError(null);
    setActionNotice(null);
    setActionCorrelation(null);
    try {
      const payload = buildOfferPayload(id, offerForm, activate);
      if (editingOffer) {
        const result = await updateOffer(user.token, editingOffer.id, payload);
        setOffers((prev) => prev.map((entry) => (entry.id === editingOffer.id ? result.data : entry)));
        setActionNotice("Оффер обновлён");
        setActionCorrelation(result.correlationId ?? null);
      } else {
        const result = await createOffer(user.token, payload);
        setOffers((prev) => [result.data, ...prev]);
        setActionNotice("Оффер создан");
        setActionCorrelation(result.correlationId ?? null);
      }
      setOfferModalOpen(false);
    } catch (err) {
      setOfferFormError(normalizeError(err, "Не удалось сохранить оффер"));
    }
  };

  const handleToggleOffer = async (offer: Offer) => {
    if (!user) return;
    setActionNotice(null);
    setActionCorrelation(null);
    try {
      if (offer.active) {
        const result = await disableOffer(user.token, offer.id);
        setOffers((prev) => prev.map((entry) => (entry.id === offer.id ? { ...entry, active: false } : entry)));
        setActionNotice("Оффер отключён");
        setActionCorrelation(result.correlationId ?? null);
      } else {
        const result = await activateOffer(user.token, offer.id);
        setOffers((prev) => prev.map((entry) => (entry.id === offer.id ? { ...entry, active: true } : entry)));
        setActionNotice("Оффер активирован");
        setActionCorrelation(result.correlationId ?? null);
      }
    } catch (err) {
      setOffersError(normalizeError(err, "Не удалось изменить статус оффера"));
    }
  };

  return (
    <div className="stack">
      <button type="button" className="link-button" onClick={() => navigate("/services")}>
        ← Назад к каталогу
      </button>
      {itemLoading ? (
        <LoadingState label="Загружаем карточку сервиса..." />
      ) : itemError ? (
        <ErrorState description={formatErrorDescription(itemError)} correlationId={itemError.correlationId} />
      ) : item ? (
        <section className="card">
          <div className="section-title">
            <div>
              <h2>{item.title}</h2>
              <div className="stack-inline">
                <StatusBadge status={item.kind} />
                <StatusBadge status={item.status} tone={resolveCatalogTone(item.status)} />
              </div>
            </div>
            {canManage ? (
              <div className="stack-inline">
                <button type="button" className="secondary" onClick={openItemModal}>
                  Edit item
                </button>
                <button type="button" className="secondary" onClick={handleToggleItem}>
                  {item.status === "ACTIVE" ? "Disable" : "Activate"}
                </button>
              </div>
            ) : null}
          </div>
          <div className="grid two">
            <div>
              <div className="label">Категория</div>
              <div>{item.category ?? "—"}</div>
            </div>
            <div>
              <div className="label">Ед. измерения</div>
              <div>{item.baseUom}</div>
            </div>
            <div>
              <div className="label">Описание</div>
              <div>{item.description ?? "—"}</div>
            </div>
            <div>
              <div className="label">Обновлено</div>
              <div>{formatDateTime(item.updatedAt)}</div>
            </div>
          </div>
        </section>
      ) : null}

      <section className="card">
        <div className="section-title">
          <div>
            <h3>Offers / Цены и доступность</h3>
            <div className="muted">Управление ценами и доступностью офферов</div>
          </div>
          {canManage ? (
            <button type="button" className="primary" onClick={() => openOfferModal()}>
              Добавить offer
            </button>
          ) : null}
        </div>
        <div className="filters">
          <label className="filter">
            Локация
            <select
              value={filters.scope}
              onChange={(event) => setFilters((prev) => ({ ...prev, scope: event.target.value }))}
            >
              <option value="all">Все локации</option>
              <option value="selected">Конкретная станция</option>
            </select>
          </label>
          {filters.scope === "selected" ? (
            <label className="filter">
              Station ID
              <input
                type="text"
                value={filters.locationId}
                onChange={(event) => setFilters((prev) => ({ ...prev, locationId: event.target.value }))}
              />
            </label>
          ) : null}
          <label className="checkbox">
            <input
              type="checkbox"
              checked={filters.activeOnly}
              onChange={(event) => setFilters((prev) => ({ ...prev, activeOnly: event.target.checked }))}
            />
            Только активные
          </label>
          <label className="filter">
            Действует на дату
            <input
              type="date"
              value={filters.date}
              onChange={(event) => setFilters((prev) => ({ ...prev, date: event.target.value }))}
            />
          </label>
        </div>
        {actionNotice ? (
          <div className="notice">
            <div>{actionNotice}</div>
            {actionCorrelation ? <div className="muted small">Correlation ID: {actionCorrelation}</div> : null}
          </div>
        ) : null}
        {offersLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : offersError ? (
          <ErrorState description={formatErrorDescription(offersError)} correlationId={offersError.correlationId} />
        ) : filteredOffers.length === 0 ? (
          <EmptyState
            title={offers.length === 0 ? "Офферов нет" : "Нет результатов фильтра"}
            description={
              offers.length === 0
                ? "Создайте первый оффер для этой услуги."
                : "Измените фильтры или сбросьте параметры."
            }
            action={
              offers.length === 0 && canManage ? (
                <button type="button" className="primary" onClick={() => openOfferModal()}>
                  Добавить offer
                </button>
              ) : (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setFilters({ scope: "all", locationId: "", activeOnly: false, date: "" })}
                >
                  Сбросить фильтры
                </button>
              )
            }
          />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Offer ID</th>
                <th>Локации</th>
                <th>Цена</th>
                <th>НДС</th>
                <th>Период</th>
                <th>Доступность</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filteredOffers.map((offer) => (
                <tr key={offer.id}>
                  <td className="mono">{offer.id.slice(0, 8)}</td>
                  <td>
                    {offer.locationScope === "all"
                      ? "Все локации"
                      : `${offer.locationIds?.length ?? 0} станций`}
                  </td>
                  <td>{formatOfferPrice(offer.price, offer.currency ?? "RUB")}</td>
                  <td>{offer.vatRate ?? "—"}</td>
                  <td>
                    {formatDate(offer.validFrom)} → {formatDate(offer.validTo)}
                  </td>
                  <td>{offer.availability.toUpperCase()}</td>
                  <td>
                    <StatusBadge status={offer.active ? "ACTIVE" : "DISABLED"} tone={resolveOfferTone(offer.active)} />
                  </td>
                  <td>
                    {canManage ? (
                      <div className="stack-inline">
                        <button type="button" className="ghost" onClick={() => openOfferModal(offer)}>
                          Edit
                        </button>
                        <button type="button" className="ghost" onClick={() => handleToggleOffer(offer)}>
                          {offer.active ? "Disable" : "Activate"}
                        </button>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {itemModalOpen && itemForm ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>Редактировать элемент</h3>
              <button type="button" className="ghost" onClick={() => setItemModalOpen(false)}>
                Close
              </button>
            </div>
            <div className="form-grid">
              <label className="form-field">
                Название *
                <input
                  type="text"
                  value={itemForm.title}
                  onChange={(event) => setItemForm((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
                />
              </label>
              <label className="form-field">
                Тип
                <select
                  value={itemForm.kind}
                  onChange={(event) =>
                    setItemForm((prev) => (prev ? { ...prev, kind: event.target.value as CatalogItemKind } : prev))
                  }
                >
                  <option value="SERVICE">SERVICE</option>
                  <option value="PRODUCT">PRODUCT</option>
                </select>
              </label>
              <label className="form-field">
                Категория
                <input
                  type="text"
                  value={itemForm.category}
                  onChange={(event) => setItemForm((prev) => (prev ? { ...prev, category: event.target.value } : prev))}
                />
              </label>
              <label className="form-field">
                Ед. измерения *
                <input
                  type="text"
                  value={itemForm.baseUom}
                  onChange={(event) => setItemForm((prev) => (prev ? { ...prev, baseUom: event.target.value } : prev))}
                />
              </label>
              <label className="form-field form-grid__full">
                Описание
                <textarea
                  className="textarea"
                  rows={3}
                  value={itemForm.description}
                  onChange={(event) => setItemForm((prev) => (prev ? { ...prev, description: event.target.value } : prev))}
                />
              </label>
              <label className="form-field">
                Статус
                <select
                  value={itemForm.status}
                  onChange={(event) =>
                    setItemForm((prev) => (prev ? { ...prev, status: event.target.value as CatalogItemStatus } : prev))
                  }
                >
                  <option value="DRAFT">DRAFT</option>
                  <option value="ACTIVE">ACTIVE</option>
                </select>
              </label>
            </div>
            {itemFormError ? (
              <div className="notice error">
                {formatErrorDescription(itemFormError)}
                {itemFormError.correlationId ? (
                  <div className="muted small">Correlation ID: {itemFormError.correlationId}</div>
                ) : null}
              </div>
            ) : null}
            <div className="form-actions">
              <button type="button" className="primary" onClick={() => handleSaveItem(false)}>
                Save
              </button>
              <button type="button" className="secondary" onClick={() => handleSaveItem(true)}>
                Save & Activate
              </button>
              <button type="button" className="ghost" onClick={() => setItemModalOpen(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {offerModalOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>{editingOffer ? "Редактировать оффер" : "Новый оффер"}</h3>
              <button type="button" className="ghost" onClick={() => setOfferModalOpen(false)}>
                Close
              </button>
            </div>
            <div className="notice">
              Изменение оффера влияет на новые заказы, не пересчитывает старые.
            </div>
            <div className="form-grid">
              <label className="form-field">
                Цена *
                <input
                  type="number"
                  value={offerForm.price}
                  onChange={(event) => setOfferForm((prev) => ({ ...prev, price: event.target.value }))}
                />
              </label>
              <label className="form-field">
                Валюта
                <select
                  value={offerForm.currency}
                  onChange={(event) => setOfferForm((prev) => ({ ...prev, currency: event.target.value }))}
                >
                  <option value="RUB">RUB</option>
                </select>
              </label>
              <label className="form-field">
                НДС
                <input
                  type="number"
                  value={offerForm.vatRate}
                  onChange={(event) => setOfferForm((prev) => ({ ...prev, vatRate: event.target.value }))}
                />
              </label>
              <label className="form-field">
                Valid from
                <input
                  type="date"
                  value={offerForm.validFrom}
                  onChange={(event) => setOfferForm((prev) => ({ ...prev, validFrom: event.target.value }))}
                />
              </label>
              <label className="form-field">
                Valid to
                <input
                  type="date"
                  value={offerForm.validTo}
                  onChange={(event) => setOfferForm((prev) => ({ ...prev, validTo: event.target.value }))}
                />
              </label>
              <label className="form-field">
                Scope
                <select
                  value={offerForm.locationScope}
                  onChange={(event) =>
                    setOfferForm((prev) => ({ ...prev, locationScope: event.target.value as OfferLocationScope }))
                  }
                >
                  <option value="all">Все локации</option>
                  <option value="selected">Выбранные станции</option>
                </select>
              </label>
              {offerForm.locationScope === "selected" ? (
                <label className="form-field form-grid__full">
                  Station IDs (через запятую)
                  <input
                    type="text"
                    value={offerForm.locationIds}
                    onChange={(event) => setOfferForm((prev) => ({ ...prev, locationIds: event.target.value }))}
                  />
                </label>
              ) : null}
              <label className="form-field">
                Availability
                <select
                  value={offerForm.availability}
                  onChange={(event) =>
                    setOfferForm((prev) => ({ ...prev, availability: event.target.value as OfferAvailability }))
                  }
                >
                  <option value="always">ALWAYS</option>
                  <option value="schedule">SCHEDULE</option>
                  <option value="capacity">CAPACITY</option>
                </select>
              </label>
            </div>
            {offerFormError ? (
              <div className="notice error">
                {formatErrorDescription(offerFormError)}
                {offerFormError.correlationId ? (
                  <div className="muted small">Correlation ID: {offerFormError.correlationId}</div>
                ) : null}
              </div>
            ) : null}
            <div className="form-actions">
              <button type="button" className="primary" onClick={() => handleSaveOffer(false)}>
                Save
              </button>
              <button type="button" className="secondary" onClick={() => handleSaveOffer(true)}>
                Save & Activate
              </button>
              <button type="button" className="ghost" onClick={() => setOfferModalOpen(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

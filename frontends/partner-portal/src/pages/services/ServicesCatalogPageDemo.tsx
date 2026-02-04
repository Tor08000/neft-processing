import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Wrench } from "../../components/icons";
import { StatusBadge } from "../../components/StatusBadge";
import { EmptyState } from "../../components/EmptyState";
import { demoCatalogItems } from "../../demo/partnerDemoData";
import type { CatalogItemStatus } from "../../types/marketplace";
import { formatDateTime, formatNumber } from "../../utils/format";

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

export function ServicesCatalogPageDemo() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState({
    q: "",
    kind: "ALL",
    status: "ALL",
  });

  const safeT = (key: string, fallback: string) => {
    const value = t(key);
    return value === key ? fallback : value;
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="page-section">
          <div className="page-section__header">
            <div>
              <h2>{safeT("servicesCatalogPage.title", "Каталог услуг")}</h2>
              <div className="muted">{safeT("servicesCatalogPage.subtitle", "Услуги и товары партнера")}</div>
            </div>
            <button type="button" className="primary" disabled>
              {safeT("actions.create", "Добавить")}
            </button>
          </div>
          <div className="page-section__content">
            <div className="filters neft-filters">
              <label className="filter neft-filter">
                {safeT("servicesCatalogPage.filters.search", "Поиск")}
                <input
                  type="search"
                  placeholder={safeT("servicesCatalogPage.filters.searchPlaceholder", "Название или категория")}
                  value={filters.q}
                  onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value }))}
                />
              </label>
              <label className="filter neft-filter">
                {safeT("servicesCatalogPage.filters.kind", "Тип")}
                <select
                  value={filters.kind}
                  onChange={(event) => setFilters((prev) => ({ ...prev, kind: event.target.value }))}
                >
                  <option value="ALL">{safeT("common.all", "Все")}</option>
                  <option value="SERVICE">{safeT("servicesCatalogPage.filters.kindOptions.service", "Услуга")}</option>
                  <option value="PRODUCT">{safeT("servicesCatalogPage.filters.kindOptions.product", "Товар")}</option>
                </select>
              </label>
              <label className="filter neft-filter">
                {safeT("servicesCatalogPage.filters.status", "Статус")}
                <select
                  value={filters.status}
                  onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
                >
                  <option value="ALL">{safeT("common.all", "Все")}</option>
                  <option value="DRAFT">{safeT("servicesCatalogPage.filters.statusOptions.draft", "Черновик")}</option>
                  <option value="ACTIVE">{safeT("servicesCatalogPage.filters.statusOptions.active", "Активен")}</option>
                  <option value="DISABLED">{safeT("servicesCatalogPage.filters.statusOptions.disabled", "Отключен")}</option>
                  <option value="ARCHIVED">{safeT("servicesCatalogPage.filters.statusOptions.archived", "Архив")}</option>
                </select>
              </label>
            </div>
          </div>
        </div>

        {demoCatalogItems.length === 0 ? (
          <EmptyState
            icon={<Wrench />}
            title={safeT("emptyStates.servicesCatalog.title", "Каталог пуст")}
            description={safeT("emptyStates.servicesCatalog.description", "Добавьте первую услугу")}
          />
        ) : (
          <div className="page-section">
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{safeT("servicesCatalogPage.table.title", "Название")}</th>
                    <th>{safeT("servicesCatalogPage.table.kind", "Тип")}</th>
                    <th>{safeT("servicesCatalogPage.table.category", "Категория")}</th>
                    <th>{safeT("servicesCatalogPage.table.status", "Статус")}</th>
                    <th>{safeT("servicesCatalogPage.table.activeOffers", "Активные офферы")}</th>
                    <th>{safeT("servicesCatalogPage.table.updatedAt", "Обновлено")}</th>
                    <th>{safeT("servicesCatalogPage.table.actions", "Действия")}</th>
                  </tr>
                </thead>
                <tbody>
                  {demoCatalogItems.map((item) => (
                    <tr key={item.id}>
                      <td>{item.title}</td>
                      <td>{item.kind}</td>
                      <td>{item.category ?? safeT("common.notAvailable", "—")}</td>
                      <td>
                        <StatusBadge status={item.status} tone={resolveCatalogTone(item.status)} />
                      </td>
                      <td>{formatNumber(item.activeOffersCount ?? null)}</td>
                      <td>{formatDateTime(item.updatedAt)}</td>
                      <td>
                        <div className="stack-inline">
                          <Link to={`/services/${item.id}`} className="link-button">
                            {safeT("common.open", "Открыть")}
                          </Link>
                          <button type="button" className="ghost" disabled>
                            {safeT("actions.edit", "Редактировать")}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination pagination-wrapper">
              <button type="button" className="secondary" disabled>
                {safeT("servicesCatalogPage.pagination.prev", "Назад")}
              </button>
              <div className="muted">{safeT("servicesCatalogPage.pagination.page", "Страница 1 из 1")}</div>
              <button type="button" className="secondary" disabled>
                {safeT("servicesCatalogPage.pagination.next", "Вперед")}
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="card import-section">
        <div className="page-section__header">
          <div>
            <h3>{safeT("servicesCatalogPage.import.title", "Импорт из CSV")}</h3>
            <div className="muted">{safeT("servicesCatalogPage.import.subtitle", "Загрузите услуги через файл")}</div>
          </div>
        </div>
        <div className="page-section__content">
          <div className="notice">
            <div>В демо загрузка CSV отключена</div>
          </div>
          <div className="form-grid neft-import-grid">
            <label className="form-field">
              {safeT("servicesCatalogPage.import.csvFile", "CSV файл")}
              <input type="file" accept=".csv,text/csv" disabled />
            </label>
            <label className="form-field">
              {safeT("servicesCatalogPage.import.mode", "Режим")}
              <select value="create" disabled>
                <option value="create">{safeT("servicesCatalogPage.import.modes.create", "Создать")}</option>
                <option value="upsert">{safeT("servicesCatalogPage.import.modes.upsert", "Обновить")}</option>
              </select>
            </label>
            <div className="form-grid__actions">
              <button type="button" className="secondary" disabled>
                {safeT("servicesCatalogPage.import.preview", "Предпросмотр")}
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

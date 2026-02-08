import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  archiveMarketplaceService,
  createMarketplaceService,
  fetchMarketplaceServices,
  submitMarketplaceService,
} from "../api/marketplaceServices";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate } from "../utils/format";
import { canManageServices, canReadServices } from "../utils/roles";
import type { MarketplaceServiceSummary } from "../types/marketplace";

export function ServicesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const canRead = canReadServices(user?.roles);
  const canManage = canManageServices(user?.roles);
  const [services, setServices] = useState<MarketplaceServiceSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({ q: "", status: "ALL", category: "" });
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    title: "",
    category: "",
    duration_min: "60",
    description: "",
    requirements: "",
    tags: "",
  });
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user || !canRead) return;
    setIsLoading(true);
    fetchMarketplaceServices(user.token, {
      q: filters.q || undefined,
      status: filters.status !== "ALL" ? filters.status : undefined,
      category: filters.category || undefined,
    })
      .then((data) => {
        if (active) {
          setServices(data.items ?? []);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить каталог услуг");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [user, canRead, filters]);

  const handleCreate = async () => {
    if (!user) return;
    if (!createForm.title.trim() || !createForm.category.trim() || !createForm.duration_min.trim()) {
      setCreateError("Заполните обязательные поля");
      return;
    }
    const durationValue = Number(createForm.duration_min);
    if (Number.isNaN(durationValue) || durationValue < 5) {
      setCreateError("Длительность должна быть числом не менее 5 минут");
      return;
    }
    setCreateError(null);
    try {
      const created = await createMarketplaceService(user.token, {
        title: createForm.title.trim(),
        description: createForm.description.trim() || null,
        category: createForm.category.trim(),
        tags: createForm.tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        attributes: {},
        duration_min: durationValue,
        requirements: createForm.requirements.trim() || null,
      });
      setCreateOpen(false);
      navigate(`/services/${created.id}`);
    } catch (err) {
      console.error(err);
      setCreateError("Не удалось создать услугу");
    }
  };

  const handleSubmit = async (serviceId: string) => {
    if (!user) return;
    try {
      await submitMarketplaceService(user.token, serviceId);
      setServices((prev) =>
        prev.map((item) => (item.id === serviceId ? { ...item, status: "PENDING_REVIEW" } : item)),
      );
    } catch (err) {
      console.error(err);
      setError("Не удалось отправить услугу на модерацию");
    }
  };

  const handleArchive = async (serviceId: string) => {
    if (!user) return;
    try {
      await archiveMarketplaceService(user.token, serviceId);
      setServices((prev) => prev.map((item) => (item.id === serviceId ? { ...item, status: "ARCHIVED" } : item)));
    } catch (err) {
      console.error(err);
      setError("Не удалось архивировать услугу");
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Каталог услуг</h2>
          <span className="muted">Marketplace v1</span>
        </div>
        <div className="filters-row">
          <input
            type="search"
            placeholder="Поиск по названию"
            value={filters.q}
            onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value }))}
          />
          <input
            type="text"
            placeholder="Категория"
            value={filters.category}
            onChange={(event) => setFilters((prev) => ({ ...prev, category: event.target.value }))}
          />
          <select
            value={filters.status}
            onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
          >
            <option value="ALL">Все статусы</option>
            <option value="DRAFT">Черновик</option>
            <option value="PENDING_REVIEW">На модерации</option>
            <option value="ACTIVE">Активно</option>
            <option value="SUSPENDED">Приостановлено</option>
            <option value="ARCHIVED">Архив</option>
          </select>
          {canManage ? (
            <button type="button" className="primary" onClick={() => setCreateOpen(true)}>
              Создать услугу
            </button>
          ) : null}
        </div>
        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <div className="error" role="alert">
            {error}
          </div>
        ) : services.length === 0 ? (
          <div className="empty-state">
            <strong>Каталог пуст</strong>
            <span className="muted">Создайте первую услугу для публикации.</span>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Услуга</th>
                <th>Категория</th>
                <th>Статус</th>
                <th>Длительность</th>
                <th>Обновлено</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {services.map((service) => (
                <tr key={service.id}>
                  <td>{service.title}</td>
                  <td>{service.category}</td>
                  <td>
                    <StatusBadge status={service.status} />
                  </td>
                  <td>{service.duration_min} мин</td>
                  <td>{formatDate(service.updated_at ?? service.created_at ?? null)}</td>
                  <td>
                    <div className="table-actions">
                      <button type="button" className="secondary" onClick={() => navigate(`/services/${service.id}`)}>
                        Открыть
                      </button>
                      {canManage ? (
                        <>
                          <button type="button" className="secondary" onClick={() => navigate(`/services/${service.id}`)}>
                            Edit
                          </button>
                          {service.status === "DRAFT" ? (
                            <button type="button" className="primary" onClick={() => handleSubmit(service.id)}>
                              Submit
                            </button>
                          ) : null}
                          {service.status !== "ARCHIVED" ? (
                            <button type="button" className="danger" onClick={() => handleArchive(service.id)}>
                              Archive
                            </button>
                          ) : null}
                        </>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      {createOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="modal-header">
              <h3>Новая услуга</h3>
              <button type="button" className="ghost" onClick={() => setCreateOpen(false)}>
                Закрыть
              </button>
            </div>
            <div className="modal-body stack">
              {createError ? (
                <div className="error" role="alert">
                  {createError}
                </div>
              ) : null}
              <label className="field">
                <span>Название</span>
                <input
                  type="text"
                  value={createForm.title}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, title: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Категория</span>
                <input
                  type="text"
                  value={createForm.category}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, category: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Длительность (мин)</span>
                <input
                  type="number"
                  min={5}
                  max={1440}
                  value={createForm.duration_min}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, duration_min: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Описание</span>
                <textarea
                  value={createForm.description}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, description: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Требования</span>
                <input
                  type="text"
                  value={createForm.requirements}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, requirements: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Теги (через запятую)</span>
                <input
                  type="text"
                  value={createForm.tags}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, tags: event.target.value }))}
                />
              </label>
            </div>
            <div className="modal-footer">
              <button type="button" className="secondary" onClick={() => setCreateOpen(false)}>
                Отмена
              </button>
              <button type="button" className="primary" onClick={handleCreate}>
                Создать
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

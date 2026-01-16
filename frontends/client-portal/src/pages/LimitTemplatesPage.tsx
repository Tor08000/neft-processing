import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api/http";
import {
  createLimitTemplate,
  fetchLimitTemplates,
  updateLimitTemplate,
  type LimitTemplate,
  type LimitTemplateLimit,
} from "../api/limitTemplates";
import { useAuth } from "../auth/AuthContext";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { StatusPage } from "../components/StatusPage";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";

const EMPTY_LIMIT: LimitTemplateLimit = { type: "AMOUNT", value: 0, window: "DAY" };

export function LimitTemplatesPage() {
  const { user } = useAuth();
  const [templates, setTemplates] = useState<LimitTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<LimitTemplate | null>(null);
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formLimits, setFormLimits] = useState<LimitTemplateLimit[]>([{ ...EMPTY_LIMIT }]);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDisable, setConfirmDisable] = useState<LimitTemplate | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast, showToast } = useToast();

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);
    fetchLimitTemplates(user)
      .then((items) => {
        if (!mounted) return;
        setTemplates(items);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status });
        } else {
          setError({ message: err instanceof Error ? err.message : "Не удалось загрузить шаблоны лимитов" });
        }
      })
      .finally(() => setIsLoading(false));
    return () => {
      mounted = false;
    };
  }, [user]);

  const activeTemplates = useMemo(() => templates.filter((item) => item.status === "ACTIVE"), [templates]);

  const resetForm = () => {
    setFormName("");
    setFormDescription("");
    setFormLimits([{ ...EMPTY_LIMIT }]);
    setFormError(null);
    setEditingTemplate(null);
  };

  const openCreate = () => {
    resetForm();
    setIsEditorOpen(true);
  };

  const openEdit = (template: LimitTemplate) => {
    setEditingTemplate(template);
    setFormName(template.name);
    setFormDescription(template.description ?? "");
    setFormLimits(
      template.limits.length
        ? template.limits.map((limit) => ({ type: limit.type, value: limit.value, window: limit.window }))
        : [{ ...EMPTY_LIMIT }],
    );
    setFormError(null);
    setIsEditorOpen(true);
  };

  const updateLimitField = (index: number, key: keyof LimitTemplateLimit, value: string) => {
    setFormLimits((prev) =>
      prev.map((limit, idx) => (idx === index ? { ...limit, [key]: key === "value" ? Number(value) : value } : limit)),
    );
  };

  const addLimitRow = () => {
    setFormLimits((prev) => [...prev, { ...EMPTY_LIMIT }]);
  };

  const removeLimitRow = (index: number) => {
    setFormLimits((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleSubmit = async () => {
    if (!formName.trim()) {
      setFormError("Укажите название шаблона.");
      return;
    }
    if (!formLimits.length || formLimits.some((limit) => !limit.value || limit.value <= 0)) {
      setFormError("Укажите корректные значения лимитов.");
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      if (editingTemplate) {
        const updated = await updateLimitTemplate(
          editingTemplate.id,
          {
            name: formName,
            description: formDescription || null,
            limits: formLimits,
          },
          user,
        );
        setTemplates((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        showToast({ kind: "success", text: "Шаблон обновлён" });
      } else {
        const created = await createLimitTemplate(
          { name: formName, description: formDescription || null, limits: formLimits },
          user,
        );
        setTemplates((prev) => [created, ...prev]);
        showToast({ kind: "success", text: "Шаблон создан" });
      }
      setIsEditorOpen(false);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        setFormError("Конфликт: шаблон уже используется.");
      } else {
        setFormError(err instanceof Error ? err.message : "Не удалось сохранить шаблон");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDisable = async () => {
    if (!confirmDisable) return;
    setIsSubmitting(true);
    try {
      const updated = await updateLimitTemplate(
        confirmDisable.id,
        { status: "DISABLED" },
        user,
      );
      setTemplates((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setConfirmDisable(null);
      showToast({ kind: "success", text: "Шаблон отключён" });
    } catch (err: unknown) {
      setConfirmDisable(null);
      showToast({ kind: "error", text: err instanceof Error ? err.message : "Не удалось отключить шаблон" });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return <AppLoadingState label="Загружаем шаблоны лимитов..." />;
  }

  if (error) {
    if (error.status === 403) {
      return <AppForbiddenState message="Недостаточно прав для работы с шаблонами лимитов." />;
    }
    if (error.status && error.status >= 500) {
      return <StatusPage title="Сервис недоступен" description="Попробуйте обновить страницу позже." />;
    }
    return <AppErrorState message={error.message} status={error.status} />;
  }

  if (!templates.length) {
    return (
      <AppEmptyState
        title="Шаблоны не созданы"
        description="Создайте шаблон лимитов, чтобы применять его к картам."
        action={<button className="primary" onClick={openCreate} type="button">Создать шаблон</button>}
      />
    );
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Шаблоны лимитов</h2>
          <p className="muted">Создавайте и применяйте шаблоны лимитов на уровне организации.</p>
        </div>
        <button type="button" className="primary" onClick={openCreate}>
          Создать шаблон
        </button>
      </div>

      {activeTemplates.length ? (
        <div className="muted">Активных шаблонов: {activeTemplates.length}</div>
      ) : (
        <div className="muted">Нет активных шаблонов.</div>
      )}

      <table className="table">
        <thead>
          <tr>
            <th>Название</th>
            <th>Описание</th>
            <th>Лимиты</th>
            <th>Статус</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {templates.map((template) => (
            <tr key={template.id}>
              <td>{template.name}</td>
              <td>{template.description ?? "—"}</td>
              <td>
                <ul className="muted bullets compact">
                  {template.limits.map((limit) => (
                    <li key={`${limit.type}-${limit.window}`}>
                      {limit.type} ({limit.window}): {limit.value}
                    </li>
                  ))}
                </ul>
              </td>
              <td>{template.status}</td>
              <td className="actions">
                <button type="button" className="ghost" onClick={() => openEdit(template)}>
                  Редактировать
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={template.status !== "ACTIVE"}
                  onClick={() => setConfirmDisable(template)}
                >
                  Отключить
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {isEditorOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{editingTemplate ? "Редактировать шаблон" : "Создать шаблон"}</h2>
            <div className="form-grid">
              <label className="form-field">
                <span>Название</span>
                <input value={formName} onChange={(event) => setFormName(event.target.value)} />
              </label>
              <label className="form-field">
                <span>Описание</span>
                <input value={formDescription} onChange={(event) => setFormDescription(event.target.value)} />
              </label>
            </div>
            <div className="stack">
              <div className="muted">Лимиты</div>
              {formLimits.map((limit, index) => (
                <div key={`limit-${index}`} className="form-grid">
                  <label className="form-field">
                    <span>Тип</span>
                    <select value={limit.type} onChange={(event) => updateLimitField(index, "type", event.target.value)}>
                      <option value="AMOUNT">AMOUNT</option>
                      <option value="LITERS">LITERS</option>
                      <option value="COUNT">COUNT</option>
                    </select>
                  </label>
                  <label className="form-field">
                    <span>Окно</span>
                    <select value={limit.window} onChange={(event) => updateLimitField(index, "window", event.target.value)}>
                      <option value="DAY">DAY</option>
                      <option value="WEEK">WEEK</option>
                      <option value="MONTH">MONTH</option>
                    </select>
                  </label>
                  <label className="form-field">
                    <span>Значение</span>
                    <input
                      type="number"
                      min={0}
                      value={limit.value}
                      onChange={(event) => updateLimitField(index, "value", event.target.value)}
                    />
                  </label>
                  <div className="actions">
                    <button type="button" className="ghost" onClick={() => removeLimitRow(index)} disabled={formLimits.length === 1}>
                      Удалить
                    </button>
                  </div>
                </div>
              ))}
              <button type="button" className="ghost" onClick={addLimitRow}>
                + Добавить лимит
              </button>
            </div>
            {formError ? <div className="error-text">{formError}</div> : null}
            <div className="actions">
              <button type="button" className="ghost" onClick={() => setIsEditorOpen(false)}>
                Отмена
              </button>
              <button type="button" className="primary" onClick={() => void handleSubmit()} disabled={isSubmitting}>
                {editingTemplate ? "Сохранить" : "Создать"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <ConfirmActionModal
        isOpen={!!confirmDisable}
        title="Отключить шаблон"
        description="Шаблон нельзя удалить, но можно отключить. Продолжить?"
        confirmLabel="Отключить"
        onConfirm={() => void handleDisable()}
        onCancel={() => setConfirmDisable(null)}
        isProcessing={isSubmitting}
        isConfirmDisabled={!confirmDisable}
      >
        <div className="muted">Шаблон: {confirmDisable?.name}</div>
      </ConfirmActionModal>

      {toast ? <Toast toast={toast} onClose={() => showToast(null)} /> : null}
    </div>
  );
}

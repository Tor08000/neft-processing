import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  blockCard,
  bulkApplyLimitTemplate,
  bulkBlockCards,
  bulkGrantCardAccess,
  bulkRevokeCardAccess,
  bulkUnblockCards,
  fetchCards,
  unblockCard,
  type BulkCardsResponse,
} from "../api/cards";
import { fetchClientUsers } from "../api/controls";
import { fetchLimitTemplates, type LimitTemplate } from "../api/limitTemplates";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import type { ClientCard } from "../types/cards";
import type { ClientUserSummary } from "../types/controls";
import { hasAnyRole } from "../utils/roles";
import { StatusPage } from "../components/StatusPage";

const DEFAULT_SCOPE = "USE";
const MAX_PREVIEW = 5;

type BulkAction = "block" | "unblock" | "grant" | "revoke" | "apply";

type BulkResult = {
  action: BulkAction;
  success: string[];
  failed: Record<string, string>;
};

export function ClientCardsPage() {
  const { user } = useAuth();
  const [cards, setCards] = useState<ClientCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeModal, setActiveModal] = useState<BulkAction | null>(null);
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkResult, setBulkResult] = useState<BulkResult | null>(null);
  const [drivers, setDrivers] = useState<ClientUserSummary[]>([]);
  const [templates, setTemplates] = useState<LimitTemplate[]>([]);
  const [selectedDriverId, setSelectedDriverId] = useState<string>("");
  const [selectedScope, setSelectedScope] = useState<string>(DEFAULT_SCOPE);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const { toast, showToast } = useToast();

  const canManageCards = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER"]);

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);
    fetchCards(user)
      .then((data) => {
        if (!mounted) return;
        setCards(data.items);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status });
        } else {
          setError({ message: err instanceof Error ? err.message : "Не удалось загрузить карты" });
        }
      })
      .finally(() => setIsLoading(false));
    return () => {
      mounted = false;
    };
  }, [user]);

  useEffect(() => {
    setSelectedIds((prev) => {
      const available = new Set(cards.map((card) => card.id));
      const next = new Set<string>();
      prev.forEach((id) => {
        if (available.has(id)) next.add(id);
      });
      return next;
    });
  }, [cards]);

  useEffect(() => {
    if (!canManageCards) return;
    fetchClientUsers(user)
      .then((response) => {
        setDrivers((response.items ?? []).filter((item) => (item.roles ?? []).some((role) => role === "CLIENT_VIEWER" || role === "CLIENT_USER" || role === "DRIVER")));
      })
      .catch(() => {
        setDrivers([]);
      });
    fetchLimitTemplates(user)
      .then((items) => {
        setTemplates(items);
      })
      .catch(() => {
        setTemplates([]);
      });
  }, [canManageCards, user]);

  const selectedCards = useMemo(() => cards.filter((card) => selectedIds.has(card.id)), [cards, selectedIds]);
  const selectedCount = selectedIds.size;
  const allSelected = cards.length > 0 && selectedCount === cards.length;

  const toggleStatus = async (card: ClientCard) => {
    const confirmMessage = card.status === "ACTIVE" ? "Заблокировать карту?" : "Разблокировать карту?";
    if (typeof window !== "undefined" && !window.confirm(confirmMessage)) {
      return;
    }
    try {
      const response =
        card.status === "ACTIVE" ? await blockCard(card.id, user) : await unblockCard(card.id, user);
      setCards((prev) => prev.map((c) => (c.id === card.id ? { ...c, status: response.status || c.status } : c)));
      showToast({
        kind: "success",
        text: card.status === "ACTIVE" ? "Карта заблокирована" : "Карта разблокирована",
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Не удалось изменить статус";
      setError({ message });
    }
  };

  const toggleCardSelection = (cardId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(cardId)) {
        next.delete(cardId);
      } else {
        next.add(cardId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    setSelectedIds(() => {
      if (allSelected) {
        return new Set();
      }
      return new Set(cards.map((card) => card.id));
    });
  };

  const openBulkModal = (action: BulkAction) => {
    setBulkError(null);
    setBulkResult(null);
    setActiveModal(action);
  };

  const handleBulkResult = (action: BulkAction, result: BulkCardsResponse) => {
    setBulkResult({ action, success: result.success, failed: result.failed });
    if (result.success.length) {
      showToast({ kind: "success", text: `Успешно: ${result.success.length}` });
    }
    if (Object.keys(result.failed).length) {
      showToast({ kind: "warning", text: `Ошибки: ${Object.keys(result.failed).length}` });
    }
  };

  const performBulkAction = async () => {
    if (!activeModal) return;
    setBulkProcessing(true);
    setBulkError(null);
    try {
      if (activeModal === "block") {
        const response = await bulkBlockCards([...selectedIds], user);
        setCards((prev) =>
          prev.map((card) => (response.success.includes(card.id) ? { ...card, status: "BLOCKED" } : card)),
        );
        handleBulkResult("block", response);
      }
      if (activeModal === "unblock") {
        const response = await bulkUnblockCards([...selectedIds], user);
        setCards((prev) =>
          prev.map((card) => (response.success.includes(card.id) ? { ...card, status: "ACTIVE" } : card)),
        );
        handleBulkResult("unblock", response);
      }
      if (activeModal === "grant") {
        if (!selectedDriverId) {
          setBulkError("Выберите водителя.");
          return;
        }
        const response = await bulkGrantCardAccess(
          { card_ids: [...selectedIds], user_id: selectedDriverId, scope: selectedScope },
          user,
        );
        handleBulkResult("grant", response);
      }
      if (activeModal === "revoke") {
        if (!selectedDriverId) {
          setBulkError("Выберите водителя.");
          return;
        }
        const response = await bulkRevokeCardAccess(
          { card_ids: [...selectedIds], user_id: selectedDriverId, scope: selectedScope },
          user,
        );
        handleBulkResult("revoke", response);
      }
      if (activeModal === "apply") {
        if (!selectedTemplateId) {
          setBulkError("Выберите шаблон лимитов.");
          return;
        }
        const response = await bulkApplyLimitTemplate(
          { card_ids: [...selectedIds], template_id: selectedTemplateId },
          user,
        );
        handleBulkResult("apply", response);
        fetchCards(user)
          .then((data) => setCards(data.items))
          .catch(() => undefined);
      }
      setActiveModal(null);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 403) {
        setError({ message: "Недостаточно прав для выполнения bulk-действий.", status: 403 });
      } else if (err instanceof ApiError && err.status >= 500) {
        setError({ message: "Сервис временно недоступен", status: err.status });
      } else if (err instanceof ApiError && err.status === 409) {
        setBulkError("Конфликт: проверьте выбранные карты или шаблон.");
      } else {
        setBulkError(err instanceof Error ? err.message : "Не удалось выполнить bulk-действие");
      }
    } finally {
      setBulkProcessing(false);
    }
  };

  if (isLoading) {
    return <AppLoadingState label="Загружаем карты..." />;
  }

  if (error) {
    if (error.status === 403) {
      return <AppForbiddenState message="Недостаточно прав для просмотра карт." />;
    }
    if (error.status && error.status >= 500) {
      return <StatusPage title="Сервис недоступен" description="Попробуйте обновить страницу позже." />;
    }
    return <AppErrorState message={error.message} status={error.status} />;
  }

  if (cards.length === 0) {
    return <AppEmptyState title="Карт нет" description="Нет карт — выпустить первую карту." />;
  }

  const previewCards = selectedCards.slice(0, MAX_PREVIEW);
  const extraCount = selectedCount - previewCards.length;

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Карты</h2>
          <p className="muted">Просмотр и управление выпущенными картами.</p>
        </div>
      </div>

      {canManageCards ? (
        <div className="card subcard">
          <div className="card__header">
            <div>
              <h3>Массовые действия</h3>
              <p className="muted">Выбрано карт: {selectedCount}</p>
            </div>
            <div className="actions">
              <button type="button" className="ghost" onClick={toggleSelectAll}>
                {allSelected ? "Снять выбор" : "Выбрать все на странице"}
              </button>
              <button type="button" className="ghost" onClick={() => setSelectedIds(new Set())}>
                Очистить выбор
              </button>
            </div>
          </div>
          <div className="actions">
            <button type="button" className="secondary" disabled={!selectedCount} onClick={() => openBulkModal("block")}>
              Заблокировать {selectedCount} карт
            </button>
            <button type="button" className="secondary" disabled={!selectedCount} onClick={() => openBulkModal("unblock")}>
              Разблокировать {selectedCount} карт
            </button>
            <button type="button" className="secondary" disabled={!selectedCount} onClick={() => openBulkModal("grant")}>
              Выдать доступ
            </button>
            <button type="button" className="secondary" disabled={!selectedCount} onClick={() => openBulkModal("revoke")}>
              Отозвать доступ
            </button>
            <button type="button" className="secondary" disabled={!selectedCount} onClick={() => openBulkModal("apply")}>
              Применить шаблон лимитов
            </button>
          </div>
          {bulkResult ? (
            <div className="card state">
              <strong>Результат bulk-действия: {bulkResult.action}</strong>
              <div className="muted">Успешно: {bulkResult.success.length}</div>
              {Object.keys(bulkResult.failed).length ? (
                <div className="muted">
                  Ошибки: {Object.keys(bulkResult.failed).length}
                  <ul className="muted bullets compact">
                    {Object.entries(bulkResult.failed).map(([cardId, reason]) => (
                      <li key={`${cardId}-${reason}`}>
                        {cardId}: {reason}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      <table className="table">
        <thead>
          <tr>
            {canManageCards ? (
              <th>
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  aria-label="Выбрать все карты"
                />
              </th>
            ) : null}
            <th>ID карты</th>
            <th>Номер</th>
            <th>Статус</th>
            <th>Лимиты</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {cards.map((card) => (
            <tr key={card.id}>
              {canManageCards ? (
                <td>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(card.id)}
                    onChange={() => toggleCardSelection(card.id)}
                    aria-label={`Выбрать карту ${card.id}`}
                  />
                </td>
              ) : null}
              <td>{card.id}</td>
              <td>{card.pan_masked ?? "—"}</td>
              <td>
                <span className={`pill pill--${card.status === "ACTIVE" ? "success" : "warning"}`}>
                  {card.status}
                </span>
              </td>
              <td>
                {card.limits?.length ? (
                  <ul className="muted bullets compact">
                    {card.limits.map((limit) => (
                      <li key={`${limit.type}-${limit.window}`}>
                        {limit.type} ({limit.window}): {limit.value}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
              <td className="actions">
                <Link className="ghost" to={`/cards/${card.id}`}>
                  Подробнее
                </Link>
                <button type="button" className="secondary" onClick={() => void toggleStatus(card)}>
                  {card.status === "ACTIVE" ? "Заблокировать" : "Разблокировать"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {toast ? <Toast toast={toast} onClose={() => showToast(null)} /> : null}

      <ConfirmActionModal
        isOpen={activeModal === "block"}
        title={`Заблокировать ${selectedCount} карт`}
        description="Вы уверены, что хотите заблокировать выбранные карты? Операция повлияет на доступ клиентов."
        confirmLabel="Заблокировать"
        onConfirm={() => void performBulkAction()}
        onCancel={() => setActiveModal(null)}
        isProcessing={bulkProcessing}
        isConfirmDisabled={!selectedCount}
      >
        <ul className="muted bullets compact">
          {previewCards.map((card) => (
            <li key={card.id}>{card.pan_masked ?? card.id}</li>
          ))}
          {extraCount > 0 ? <li>и еще {extraCount}</li> : null}
        </ul>
        {bulkError ? <div className="error-text">{bulkError}</div> : null}
      </ConfirmActionModal>

      <ConfirmActionModal
        isOpen={activeModal === "unblock"}
        title={`Разблокировать ${selectedCount} карт`}
        description="Вы уверены, что хотите разблокировать выбранные карты?"
        confirmLabel="Разблокировать"
        onConfirm={() => void performBulkAction()}
        onCancel={() => setActiveModal(null)}
        isProcessing={bulkProcessing}
        isConfirmDisabled={!selectedCount}
      >
        <ul className="muted bullets compact">
          {previewCards.map((card) => (
            <li key={card.id}>{card.pan_masked ?? card.id}</li>
          ))}
          {extraCount > 0 ? <li>и еще {extraCount}</li> : null}
        </ul>
        {bulkError ? <div className="error-text">{bulkError}</div> : null}
      </ConfirmActionModal>

      <ConfirmActionModal
        isOpen={activeModal === "grant"}
        title="Выдать доступ на выбранные карты"
        description={`Вы уверены, что хотите выдать доступ на ${selectedCount} карт?`}
        confirmLabel="Выдать доступ"
        onConfirm={() => void performBulkAction()}
        onCancel={() => setActiveModal(null)}
        isProcessing={bulkProcessing}
        isConfirmDisabled={!selectedCount}
      >
        <label className="form-field">
          <span>Водитель</span>
          <select value={selectedDriverId} onChange={(event) => setSelectedDriverId(event.target.value)}>
            <option value="">Выберите пользователя</option>
            {drivers.map((driver) => (
              <option key={driver.user_id} value={driver.user_id}>
                {driver.email ?? driver.user_id}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span>Scope</span>
          <select value={selectedScope} onChange={(event) => setSelectedScope(event.target.value)}>
            <option value="USE">USE</option>
            <option value="VIEW">VIEW</option>
          </select>
        </label>
        {bulkError ? <div className="error-text">{bulkError}</div> : null}
      </ConfirmActionModal>

      <ConfirmActionModal
        isOpen={activeModal === "revoke"}
        title="Отозвать доступ на выбранные карты"
        description={`Вы уверены, что хотите отозвать доступ на ${selectedCount} карт?`}
        confirmLabel="Отозвать доступ"
        onConfirm={() => void performBulkAction()}
        onCancel={() => setActiveModal(null)}
        isProcessing={bulkProcessing}
        isConfirmDisabled={!selectedCount}
      >
        <label className="form-field">
          <span>Водитель</span>
          <select value={selectedDriverId} onChange={(event) => setSelectedDriverId(event.target.value)}>
            <option value="">Выберите пользователя</option>
            {drivers.map((driver) => (
              <option key={driver.user_id} value={driver.user_id}>
                {driver.email ?? driver.user_id}
              </option>
            ))}
          </select>
        </label>
        {bulkError ? <div className="error-text">{bulkError}</div> : null}
      </ConfirmActionModal>

      <ConfirmActionModal
        isOpen={activeModal === "apply"}
        title="Применить шаблон лимитов"
        description={`Вы уверены, что хотите применить шаблон к ${selectedCount} картам?`}
        confirmLabel="Применить"
        onConfirm={() => void performBulkAction()}
        onCancel={() => setActiveModal(null)}
        isProcessing={bulkProcessing}
        isConfirmDisabled={!selectedCount}
      >
        <label className="form-field">
          <span>Шаблон</span>
          <select value={selectedTemplateId} onChange={(event) => setSelectedTemplateId(event.target.value)}>
            <option value="">Выберите шаблон</option>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.name}
              </option>
            ))}
          </select>
        </label>
        {bulkError ? <div className="error-text">{bulkError}</div> : null}
      </ConfirmActionModal>
    </div>
  );
}

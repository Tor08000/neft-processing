import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { createMarketplaceOrder, sendMarketplaceClientEvents } from "../api/marketplace";
import { useAuth } from "../auth/AuthContext";
import type { MarketplaceOffer } from "../types/marketplace";
import { ApiError } from "../api/http";
import { formatMoney } from "../utils/format";

interface CreateMarketplaceOrderModalProps {
  serviceId: string;
  serviceTitle: string;
  offers: MarketplaceOffer[];
  onClose: () => void;
}

type SubmitStatus = "idle" | "submitting" | "success" | "error";

export function CreateMarketplaceOrderModal({
  serviceId,
  serviceTitle,
  offers,
  onClose,
}: CreateMarketplaceOrderModalProps) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [selectedOfferId, setSelectedOfferId] = useState("");
  const [qty, setQty] = useState("1");
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<SubmitStatus>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [orderId, setOrderId] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  useEffect(() => {
    if (offers.length > 0) {
      setSelectedOfferId(offers[0].id);
    }
  }, [offers]);

  const qtyValue = useMemo(() => {
    const parsed = Number(qty);
    if (Number.isNaN(parsed) || parsed <= 0) return 1;
    return parsed;
  }, [qty]);

  const handleSubmit = async () => {
    if (!user) {
      setStatus("error");
      setMessage("Недостаточно прав для оформления заказа.");
      return;
    }
    if (!selectedOfferId) {
      setStatus("error");
      setMessage("Выберите оффер для заказа.");
      return;
    }
    const confirmed = window.confirm("Оформить заказ на выбранную услугу?");
    if (!confirmed) return;
    setStatus("submitting");
    setMessage(null);
    setCorrelationId(null);
    setErrorStatus(null);
    try {
      const response = await createMarketplaceOrder(user, {
        items: [{ offer_id: selectedOfferId, qty: qtyValue }],
        payment_method: "NEFT_INTERNAL",
      });
      const newOrderId = response.data.id ?? null;
      if (newOrderId) {
        void sendMarketplaceClientEvents(user, [
          {
            event_type: "marketplace.order_created",
            entity_type: "ORDER",
            entity_id: newOrderId,
            source: "client_portal",
            page: location.pathname,
            payload: {
              service_id: serviceId,
              offer_id: selectedOfferId,
              qty: qtyValue,
            },
          },
        ]).catch(() => undefined);
      }
      setOrderId(newOrderId);
      setCorrelationId(response.correlationId);
      setStatus("success");
      setMessage("Заказ создан. Перенаправляем в детали заказа.");
      if (newOrderId) {
        window.setTimeout(() => {
          navigate(`/marketplace/orders/${newOrderId}`);
        }, 1200);
      }
    } catch (err) {
      const fallback = "Не удалось оформить заказ. Попробуйте позже.";
      if (err instanceof ApiError) {
        setErrorStatus(err.status);
        setCorrelationId(err.correlationId);
        setMessage(err.message || fallback);
      } else if (err instanceof Error) {
        setMessage(err.message || fallback);
      } else {
        setMessage(fallback);
      }
      setStatus("error");
    }
  };

  const selectedOffer = offers.find((offer) => offer.id === selectedOfferId);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="section-title">
          <h3>Оформить заказ</h3>
          <button type="button" className="secondary" onClick={onClose}>
            Закрыть
          </button>
        </div>

        <div className="stack">
          <div>
            <div className="muted small">Услуга</div>
            <strong>{serviceTitle}</strong>
          </div>
          <label className="filter">
            <span>Выбранный оффер</span>
            <select value={selectedOfferId} onChange={(event) => setSelectedOfferId(event.target.value)}>
              {offers.map((offer) => (
                <option key={offer.id} value={offer.id}>
                  {offer.location_name ?? "Локация не указана"} ·{" "}
                  {offer.price !== undefined && offer.price !== null
                    ? formatMoney(offer.price, offer.currency ?? "RUB")
                    : "Цена по запросу"}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            <span>Количество</span>
            <input type="number" min="1" value={qty} onChange={(event) => setQty(event.target.value)} />
          </label>
          <label className="filter">
            <span>Комментарий</span>
            <textarea
              rows={3}
              value={comment}
              placeholder="Опционально"
              onChange={(event) => setComment(event.target.value)}
            />
          </label>

          {selectedOffer ? (
            <div className="card muted-card">
              <div className="muted small">Детали оффера</div>
              <div className="stack">
                <div>
                  Цена:{" "}
                  {selectedOffer.price !== undefined && selectedOffer.price !== null
                    ? formatMoney(selectedOffer.price, selectedOffer.currency ?? "RUB")
                    : "Цена по запросу"}
                </div>
                <div>Локация: {selectedOffer.location_name ?? "—"}</div>
                <div>Условия: {selectedOffer.conditions ?? "—"}</div>
              </div>
            </div>
          ) : null}

          {status === "error" && message ? (
            <div className="card error-card">
              <strong>Ошибка</strong>
              <div>{message}</div>
              {errorStatus ? <div className="muted small">HTTP {errorStatus}</div> : null}
              {correlationId ? <div className="muted small">Correlation ID: {correlationId}</div> : null}
            </div>
          ) : null}

          {status === "success" && message ? (
            <div className="card success-card">
              <strong>Успешно</strong>
              <div>{message}</div>
              {correlationId ? <div className="muted small">Correlation ID: {correlationId}</div> : null}
              {orderId ? (
                <button type="button" className="link-button" onClick={() => navigate(`/marketplace/orders/${orderId}`)}>
                  Перейти к заказу
                </button>
              ) : null}
            </div>
          ) : null}

          <div className="actions">
            <button type="button" className="primary" onClick={handleSubmit} disabled={status === "submitting"}>
              {status === "submitting" ? "Отправляем..." : "Оформить заказ"}
            </button>
            <button type="button" className="secondary" onClick={onClose}>
              Отмена
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

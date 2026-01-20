import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchClientInvoiceDetails, initPaymentIntakeAttachment, submitPaymentIntake } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import type { ClientInvoiceDetails, ClientPaymentIntake } from "../types/portal";
import { MoneyValue } from "../components/common/MoneyValue";
import { AppErrorState, AppLoadingState } from "../components/states";
import { formatDate, formatDateTime, formatNumberParts } from "../utils/format";
import { getInvoiceStatusLabel, getInvoiceStatusTone } from "../utils/invoices";

const BANK_DETAILS = {
  recipient: "ООО «Нефть»",
  inn: "7700000000",
  kpp: "770001001",
  bank: "АО «Надежный банк»",
  bik: "044525225",
  account: "40702810900000000001",
  corrAccount: "30101810400000000225",
};

export function ClientInvoiceDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [invoice, setInvoice] = useState<ClientInvoiceDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [paidAt, setPaidAt] = useState("");
  const [bankReference, setBankReference] = useState("");
  const [comment, setComment] = useState("");
  const [proofFile, setProofFile] = useState<File | null>(null);

  useEffect(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    fetchClientInvoiceDetails(user, id)
      .then((data) => setInvoice(data))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [id, user]);

  if (!id) {
    return null;
  }

  if (isLoading) {
    return <AppLoadingState />;
  }

  if (error) {
    return <AppErrorState message={error} />;
  }

  if (!invoice) {
    return <AppErrorState message="Инвойс не найден" />;
  }

  const intakeList = invoice.payment_intakes ?? [];
  const payments = invoice.payments ?? [];
  const refunds = invoice.refunds ?? [];
  const latestIntake = intakeList[0];
  const defaultAmount = Number(invoice.amount_due ?? invoice.amount_total ?? 0);
  const invoiceCurrency = invoice.currency ?? "RUB";
  const usageLines = invoice.lines?.filter((line) => line.line_type === "USAGE") ?? [];
  const subscriptionStatusLabels: Record<string, string> = {
    ACTIVE: "Активна",
    OVERDUE: "Просрочена",
    SUSPENDED: "Приостановлена",
    CANCELED: "Отменена",
    TRIAL: "Триал",
  };
  const subscriptionStatusLabel = invoice.subscription_status
    ? subscriptionStatusLabels[invoice.subscription_status] ?? invoice.subscription_status
    : "—";
  const formatQuantity = (value?: number | null) => {
    if (value === null || value === undefined) return "—";
    const fixed = value.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
    const fractionLength = fixed.includes(".") ? fixed.split(".")[1]?.length ?? 0 : 0;
    const digits = fractionLength === 0 ? 0 : fractionLength <= 2 ? 2 : 6;
    const parts = formatNumberParts(value, digits);
    return parts.fraction ? `${parts.int}.${parts.fraction}` : parts.int;
  };

  const handleSubmitPaymentIntake = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!id || !invoice) return;
    setIsSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);
    try {
      const resolvedAmount = Number(amount || defaultAmount);
      if (!resolvedAmount || Number.isNaN(resolvedAmount)) {
        setSubmitError("Укажите сумму платежа.");
        return;
      }
      let proof:
        | {
            object_key: string;
            file_name: string;
            content_type: string;
            size: number;
          }
        | null = null;
      if (proofFile) {
        const init = await initPaymentIntakeAttachment(user, id, {
          file_name: proofFile.name,
          content_type: proofFile.type,
          size: proofFile.size,
        });
        await fetch(init.upload_url, {
          method: "PUT",
          body: proofFile,
          headers: { "Content-Type": proofFile.type },
        });
        proof = {
          object_key: init.object_key,
          file_name: proofFile.name,
          content_type: proofFile.type,
          size: proofFile.size,
        };
      }
      const result = await submitPaymentIntake(user, id, {
        amount: resolvedAmount,
        currency: invoiceCurrency,
        paid_at_claimed: paidAt || undefined,
        bank_reference: bankReference || undefined,
        comment: comment || undefined,
        proof,
      });
      const updatedIntakes = [result, ...(invoice.payment_intakes ?? [])];
      setInvoice({ ...invoice, payment_intakes: updatedIntakes });
      setSubmitSuccess("Заявка отправлена. Статус: на проверке.");
      setProofFile(null);
      setComment("");
      setBankReference("");
      setPaidAt("");
      setAmount("");
    } catch (err) {
      setSubmitError((err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderIntakeStatus = (intake: ClientPaymentIntake) => {
    if (intake.status === "APPROVED") return "Подтверждено";
    if (intake.status === "REJECTED") return "Отклонено";
    if (intake.status === "UNDER_REVIEW") return "На проверке";
    return "Отправлено";
  };

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Счёт #{invoice.id}</h2>
            <p className="muted">Инвойс за период {formatDate(invoice.period_start)} — {formatDate(invoice.period_end)}</p>
          </div>
          <div className="actions">
            <Link className="ghost" to="/invoices">
              Назад к списку
            </Link>
            {invoice.download_url ? (
              <a className="ghost" href={invoice.download_url} rel="noreferrer" target="_blank">
                Скачать PDF
              </a>
            ) : null}
          </div>
        </div>
        <div className="stats-grid">
          <div className="stat">
            <span className="muted">Статус</span>
            <strong className={`neft-chip neft-chip-${getInvoiceStatusTone(invoice.status)}`}>
              {getInvoiceStatusLabel(invoice.status)}
            </strong>
          </div>
          <div className="stat">
            <span className="muted">Сумма</span>
            <strong>
              <MoneyValue amount={invoice.amount_total ?? 0} currency={invoiceCurrency} />
            </strong>
          </div>
          <div className="stat">
            <span className="muted">Оплачено</span>
            <strong>
              <MoneyValue amount={invoice.amount_paid ?? 0} currency={invoiceCurrency} />
            </strong>
          </div>
          <div className="stat">
            <span className="muted">Остаток</span>
            <strong>
              <MoneyValue amount={invoice.amount_due ?? 0} currency={invoiceCurrency} />
            </strong>
          </div>
          <div className="stat">
            <span className="muted">Срок оплаты</span>
            <strong>{invoice.due_at ? formatDate(invoice.due_at) : "—"}</strong>
          </div>
          <div className="stat">
            <span className="muted">Дата приостановки</span>
            <strong>{invoice.suspend_at ? formatDate(invoice.suspend_at) : "—"}</strong>
          </div>
          <div className="stat">
            <span className="muted">Статус подписки</span>
            <strong>{subscriptionStatusLabel}</strong>
          </div>
        </div>
      </div>

      <section className="card">
        <div className="card__header">
          <div>
            <h3>Оплата по реквизитам</h3>
            <p className="muted">Оплатите счет банковским переводом и отправьте подтверждение.</p>
          </div>
        </div>
        <div className="form-grid">
          <div className="form-field">
            <span className="muted">Получатель</span>
            <strong>{BANK_DETAILS.recipient}</strong>
          </div>
          <div className="form-field">
            <span className="muted">ИНН / КПП</span>
            <strong>{BANK_DETAILS.inn} / {BANK_DETAILS.kpp}</strong>
          </div>
          <div className="form-field">
            <span className="muted">Банк</span>
            <strong>{BANK_DETAILS.bank}</strong>
          </div>
          <div className="form-field">
            <span className="muted">БИК</span>
            <strong>{BANK_DETAILS.bik}</strong>
          </div>
          <div className="form-field">
            <span className="muted">Р/с</span>
            <strong>{BANK_DETAILS.account}</strong>
          </div>
          <div className="form-field">
            <span className="muted">К/с</span>
            <strong>{BANK_DETAILS.corrAccount}</strong>
          </div>
          <div className="form-field form-grid__full">
            <span className="muted">Назначение платежа</span>
            <strong>Оплата счета №{id}</strong>
          </div>
          <div className="form-field">
            <span className="muted">Сумма</span>
            <strong>
              <MoneyValue amount={defaultAmount} currency={invoiceCurrency} />
            </strong>
          </div>
          <div className="form-field">
            <span className="muted">Срок оплаты</span>
            <strong>{invoice.due_at ? formatDate(invoice.due_at) : "—"}</strong>
          </div>
        </div>

        <form className="form-grid" onSubmit={handleSubmitPaymentIntake} style={{ marginTop: 16 }}>
          <label className="form-field">
            Сумма
            <input
              type="number"
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder={String(defaultAmount)}
            />
          </label>
          <label className="form-field">
            Дата оплаты
            <input type="date" value={paidAt} onChange={(event) => setPaidAt(event.target.value)} />
          </label>
          <label className="form-field">
            Номер платежки
            <input value={bankReference} onChange={(event) => setBankReference(event.target.value)} />
          </label>
          <label className="form-field form-grid__full">
            Комментарий
            <textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={3} />
          </label>
          <label className="form-field form-grid__full">
            Платежный документ (PDF/JPG/PNG)
            <input type="file" accept=".pdf,image/jpeg,image/png" onChange={(event) => setProofFile(event.target.files?.[0] ?? null)} />
          </label>
          <div className="form-actions form-grid__full">
            <button className="primary" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Отправляем..." : "Сообщить об оплате"}
            </button>
            {latestIntake ? <span className="muted">Статус: {renderIntakeStatus(latestIntake)}</span> : null}
          </div>
          {submitError ? <div className="error-text form-grid__full">{submitError}</div> : null}
          {submitSuccess ? <div className="success form-grid__full" style={{ padding: 12 }}>{submitSuccess}</div> : null}
        </form>

        {intakeList.length ? (
          <div style={{ marginTop: 16 }}>
            <h4>Отправленные подтверждения</h4>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Сумма</th>
                  <th>Статус</th>
                  <th>Комментарий</th>
                </tr>
              </thead>
              <tbody>
                {intakeList.map((intake) => (
                  <tr key={intake.id}>
                    <td>{formatDateTime(intake.created_at)}</td>
                    <td>
                      <MoneyValue amount={intake.amount} currency={intake.currency ?? invoiceCurrency} />
                    </td>
                    <td>{renderIntakeStatus(intake)}</td>
                    <td>{intake.review_note ?? intake.comment ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <section className="card">
        <div className="card__header">
          <h3>Платежи</h3>
        </div>
        {payments.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Провайдер</th>
                <th>Ссылка</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((payment) => (
                <tr key={`${payment.external_ref}-${payment.created_at}`}>
                  <td>{formatDateTime(payment.created_at)}</td>
                  <td>
                    <MoneyValue amount={payment.amount} currency={invoiceCurrency} />
                  </td>
                  <td>{payment.status}</td>
                  <td>{payment.provider ?? "—"}</td>
                  <td>{payment.external_ref ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Платежей пока нет.</p>
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <h3>Начисления за использование</h3>
        </div>
        {usageLines.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Описание</th>
                <th>Количество</th>
                <th>Цена за единицу</th>
                <th>Сумма</th>
              </tr>
            </thead>
            <tbody>
              {usageLines.map((line, index) => (
                <tr key={`${line.ref_code ?? "usage"}-${index}`}>
                  <td>{line.description ?? line.ref_code ?? "Usage"}</td>
                  <td>
                    {formatQuantity(line.quantity ?? undefined)}
                    {line.unit ? ` ${line.unit}` : ""}
                  </td>
                  <td>
                    {line.unit_price !== null && line.unit_price !== undefined ? (
                      <MoneyValue amount={line.unit_price} currency={invoiceCurrency} />
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {line.amount !== null && line.amount !== undefined ? (
                      <MoneyValue amount={line.amount} currency={invoiceCurrency} />
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Начислений за использование пока нет.</p>
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <h3>Возвраты</h3>
        </div>
        {refunds.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Причина</th>
              </tr>
            </thead>
            <tbody>
              {refunds.map((refund) => (
                <tr key={`${refund.external_ref}-${refund.created_at}`}>
                  <td>{formatDateTime(refund.created_at)}</td>
                  <td>
                    <MoneyValue amount={refund.amount} currency={invoiceCurrency} />
                  </td>
                  <td>{refund.status}</td>
                  <td>{refund.reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Возвратов пока нет.</p>
        )}
      </section>
    </div>
  );
}

import { useCallback, useMemo, useState } from "react";
import {
  ackErpStubExport,
  createBankStubPayment,
  createErpStubExport,
  generateBankStubStatement,
  getBankStubStatement,
  getErpStubExport,
} from "../../api/stubs";
import type { BankStubStatement, ErpStubExport, ErpStubExportType } from "../../types/stubs";

const exportTypes: ErpStubExportType[] = ["INVOICES", "PAYMENTS", "SETTLEMENT", "RECONCILIATION"];

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : "—");

const parseList = (raw: string) =>
  raw
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

const StubProvidersPage = () => {
  const [invoiceId, setInvoiceId] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentKey, setPaymentKey] = useState("");
  const [paymentResult, setPaymentResult] = useState<string | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [statementFrom, setStatementFrom] = useState("");
  const [statementTo, setStatementTo] = useState("");
  const [statementResult, setStatementResult] = useState<BankStubStatement | null>(null);
  const [statementIdLookup, setStatementIdLookup] = useState("");
  const [statementError, setStatementError] = useState<string | null>(null);

  const [exportType, setExportType] = useState<ErpStubExportType>("SETTLEMENT");
  const [exportEntityIds, setExportEntityIds] = useState("");
  const [exportFrom, setExportFrom] = useState("");
  const [exportTo, setExportTo] = useState("");
  const [exportRef, setExportRef] = useState("");
  const [exportResult, setExportResult] = useState<ErpStubExport | null>(null);
  const [exportIdLookup, setExportIdLookup] = useState("");
  const [exportError, setExportError] = useState<string | null>(null);

  const handleCreatePayment = useCallback(async () => {
    setPaymentResult(null);
    setPaymentError(null);
    try {
      const payload = {
        invoice_id: invoiceId,
        amount: paymentAmount ? Number(paymentAmount) : undefined,
        idempotency_key: paymentKey || undefined,
      };
      const payment = await createBankStubPayment(payload);
      setPaymentResult(`Payment ${payment.payment_ref} (${payment.status}) created`);
    } catch (error) {
      setPaymentError((error as Error).message);
    }
  }, [invoiceId, paymentAmount, paymentKey]);

  const handleGenerateStatement = useCallback(async () => {
    setStatementError(null);
    try {
      const statement = await generateBankStubStatement({ from: statementFrom, to: statementTo });
      setStatementResult(statement);
      setStatementIdLookup(statement.id);
    } catch (error) {
      setStatementError((error as Error).message);
    }
  }, [statementFrom, statementTo]);

  const handleLookupStatement = useCallback(async () => {
    setStatementError(null);
    try {
      const statement = await getBankStubStatement(statementIdLookup);
      setStatementResult(statement);
    } catch (error) {
      setStatementError((error as Error).message);
    }
  }, [statementIdLookup]);

  const handleCreateExport = useCallback(async () => {
    setExportError(null);
    try {
      const payload = {
        export_type: exportType,
        entity_ids: exportEntityIds ? parseList(exportEntityIds) : undefined,
        period_from: exportFrom || undefined,
        period_to: exportTo || undefined,
        export_ref: exportRef || undefined,
      };
      const exportItem = await createErpStubExport(payload);
      setExportResult(exportItem);
      setExportIdLookup(exportItem.id);
    } catch (error) {
      setExportError((error as Error).message);
    }
  }, [exportType, exportEntityIds, exportFrom, exportTo, exportRef]);

  const handleLookupExport = useCallback(async () => {
    setExportError(null);
    try {
      const exportItem = await getErpStubExport(exportIdLookup);
      setExportResult(exportItem);
    } catch (error) {
      setExportError((error as Error).message);
    }
  }, [exportIdLookup]);

  const handleAckExport = useCallback(async () => {
    setExportError(null);
    try {
      const exportItem = await ackErpStubExport(exportIdLookup);
      setExportResult(exportItem);
    } catch (error) {
      setExportError((error as Error).message);
    }
  }, [exportIdLookup]);

  const statementLines = useMemo(() => statementResult?.lines ?? [], [statementResult]);
  const exportItems = useMemo(() => exportResult?.items ?? [], [exportResult]);

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>Stub providers</h1>
            <p className="muted">Create mock bank payments, statements, and ERP exports for local demos.</p>
          </div>
        </div>
      </section>

      <section className="card stack">
        <header>
          <h2 style={{ fontSize: 18, fontWeight: 600 }}>Bank Stub</h2>
          <p className="muted">Capture a payment for a billing invoice and generate a statement.</p>
        </header>

        <div className="grid" style={{ gap: 16 }}>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Invoice ID</label>
            <input value={invoiceId} onChange={(event) => setInvoiceId(event.target.value)} />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Amount (optional)</label>
            <input
              type="number"
              value={paymentAmount}
              onChange={(event) => setPaymentAmount(event.target.value)}
            />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Idempotency key (optional)</label>
            <input value={paymentKey} onChange={(event) => setPaymentKey(event.target.value)} />
          </div>
        </div>
        <div className="stack-inline" style={{ gap: 12 }}>
          <button type="button" className="neft-btn" onClick={handleCreatePayment} disabled={!invoiceId}>
            Create payment
          </button>
          {paymentResult && <span className="muted">{paymentResult}</span>}
          {paymentError && <span className="muted">{paymentError}</span>}
        </div>

        <div className="divider" />

        <div className="grid" style={{ gap: 16 }}>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Statement period from</label>
            <input
              type="datetime-local"
              value={statementFrom}
              onChange={(event) => setStatementFrom(event.target.value)}
            />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Statement period to</label>
            <input
              type="datetime-local"
              value={statementTo}
              onChange={(event) => setStatementTo(event.target.value)}
            />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Statement ID</label>
            <input value={statementIdLookup} onChange={(event) => setStatementIdLookup(event.target.value)} />
          </div>
        </div>
        <div className="stack-inline" style={{ gap: 12 }}>
          <button
            type="button"
            className="neft-btn"
            onClick={handleGenerateStatement}
            disabled={!statementFrom || !statementTo}
          >
            Generate statement
          </button>
          <button
            type="button"
            className="neft-btn-secondary"
            onClick={handleLookupStatement}
            disabled={!statementIdLookup}
          >
            View statement
          </button>
          {statementError && <span className="muted">{statementError}</span>}
        </div>

        {statementResult && (
          <div className="card" style={{ padding: 16 }}>
            <div className="stack" style={{ gap: 4 }}>
              <div>
                <strong>ID:</strong> {statementResult.id}
              </div>
              <div>
                <strong>Period:</strong> {formatDate(statementResult.period_from)} → {formatDate(statementResult.period_to)}
              </div>
              <div>
                <strong>Checksum:</strong> {statementResult.checksum}
              </div>
            </div>
            <div className="divider" />
            <div className="stack">
              {statementLines.length === 0 ? (
                <div className="muted">No statement lines yet.</div>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Payment ref</th>
                      <th>Invoice</th>
                      <th>Amount</th>
                      <th>Currency</th>
                      <th>Posted at</th>
                    </tr>
                  </thead>
                  <tbody>
                    {statementLines.map((line) => (
                      <tr key={line.payment_ref}>
                        <td>{line.payment_ref}</td>
                        <td>{line.invoice_number ?? "—"}</td>
                        <td>{line.amount}</td>
                        <td>{line.currency}</td>
                        <td>{formatDate(line.posted_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </section>

      <section className="card stack">
        <header>
          <h2 style={{ fontSize: 18, fontWeight: 600 }}>ERP Stub</h2>
          <p className="muted">Export accounting packages and acknowledge receipt.</p>
        </header>

        <div className="grid" style={{ gap: 16 }}>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Export type</label>
            <select value={exportType} onChange={(event) => setExportType(event.target.value as ErpStubExportType)}>
              {exportTypes.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Entity IDs (comma separated)</label>
            <input value={exportEntityIds} onChange={(event) => setExportEntityIds(event.target.value)} />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Period from</label>
            <input type="datetime-local" value={exportFrom} onChange={(event) => setExportFrom(event.target.value)} />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Period to</label>
            <input type="datetime-local" value={exportTo} onChange={(event) => setExportTo(event.target.value)} />
          </div>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Export ref (optional)</label>
            <input value={exportRef} onChange={(event) => setExportRef(event.target.value)} />
          </div>
        </div>

        <div className="stack-inline" style={{ gap: 12 }}>
          <button type="button" className="neft-btn" onClick={handleCreateExport}>
            Create export
          </button>
        </div>

        <div className="divider" />

        <div className="grid" style={{ gap: 16 }}>
          <div className="stack" style={{ gap: 8 }}>
            <label className="muted">Export ID</label>
            <input value={exportIdLookup} onChange={(event) => setExportIdLookup(event.target.value)} />
          </div>
          <div className="stack-inline" style={{ gap: 12, alignItems: "flex-end" }}>
            <button
              type="button"
              className="neft-btn-secondary"
              onClick={handleLookupExport}
              disabled={!exportIdLookup}
            >
              View export
            </button>
            <button type="button" className="neft-btn" onClick={handleAckExport} disabled={!exportIdLookup}>
              ACK export
            </button>
            {exportError && <span className="muted">{exportError}</span>}
          </div>
        </div>

        {exportResult && (
          <div className="card" style={{ padding: 16 }}>
            <div className="stack" style={{ gap: 4 }}>
              <div>
                <strong>ID:</strong> {exportResult.id}
              </div>
              <div>
                <strong>Ref:</strong> {exportResult.export_ref}
              </div>
              <div>
                <strong>Status:</strong> {exportResult.status}
              </div>
              <div>
                <strong>Payload hash:</strong> {exportResult.payload_hash}
              </div>
            </div>
            <div className="divider" />
            {exportItems.length === 0 ? (
              <div className="muted">No export items yet.</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Entity type</th>
                    <th>Entity ID</th>
                    <th>Created at</th>
                  </tr>
                </thead>
                <tbody>
                  {exportItems.map((item) => (
                    <tr key={`${item.entity_type}-${item.entity_id}`}>
                      <td>{item.entity_type}</td>
                      <td>{item.entity_id}</td>
                      <td>{formatDate(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>
    </div>
  );
};

export default StubProvidersPage;

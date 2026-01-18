import { useMemo, useState } from "react";
import {
  createFixtureBundle,
  createFixtureImport,
  completeStatementImport,
  type ReconciliationFixtureBundle,
  type ReconciliationFixtureFormat,
  type ReconciliationFixtureImportResult,
  type ReconciliationFixtureScenario,
  type ReconciliationFixtureWrongAmountMode,
} from "../../api/reconciliation";
import { UnauthorizedError } from "../../api/client";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";

const scenarioOptions: { value: ReconciliationFixtureScenario; label: string }[] = [
  { value: "SCN2_WRONG_AMOUNT", label: "SCN-2 Wrong amount" },
  { value: "SCN2_UNMATCHED", label: "SCN-2 Unmatched" },
  { value: "SCN3_DOUBLE_PAYMENT", label: "SCN-3 Double payment" },
];

const formatOptions: { value: ReconciliationFixtureFormat; label: string }[] = [
  { value: "CSV", label: "CSV" },
  { value: "CLIENT_BANK_1C", label: "1C Client-Bank" },
  { value: "MT940", label: "MT940" },
  { value: "ALL", label: "All formats" },
];

const wrongAmountOptions: { value: ReconciliationFixtureWrongAmountMode; label: string }[] = [
  { value: "LESS", label: "Less than invoice" },
  { value: "MORE", label: "More than invoice" },
];

export function ReconciliationFixturesPage() {
  const { toast, showToast } = useToast();
  const [scenario, setScenario] = useState<ReconciliationFixtureScenario>("SCN2_WRONG_AMOUNT");
  const [invoiceId, setInvoiceId] = useState("");
  const [orgId, setOrgId] = useState("");
  const [currency, setCurrency] = useState("RUB");
  const [format, setFormat] = useState<ReconciliationFixtureFormat>("ALL");
  const [wrongAmountMode, setWrongAmountMode] = useState<ReconciliationFixtureWrongAmountMode>("LESS");
  const [amountDelta, setAmountDelta] = useState("1000");
  const [payerInn, setPayerInn] = useState("");
  const [payerName, setPayerName] = useState("");
  const [seed, setSeed] = useState("");
  const [bundle, setBundle] = useState<ReconciliationFixtureBundle | null>(null);
  const [importByFile, setImportByFile] = useState<Record<string, ReconciliationFixtureImportResult>>({});
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const showWrongAmountSettings = useMemo(() => scenario.startsWith("SCN2"), [scenario]);

  const handleGenerate = async () => {
    setError(null);
    setUnauthorized(false);
    setNotAvailable(false);

    if (!invoiceId.trim() || !orgId.trim()) {
      setError("Invoice ID and Org ID are required");
      return;
    }

    const orgIdValue = Number(orgId);
    if (!Number.isFinite(orgIdValue) || orgIdValue <= 0) {
      setError("Org ID must be a positive number");
      return;
    }

    const payload: {
      scenario: ReconciliationFixtureScenario;
      invoice_id: string;
      org_id: number;
      format: ReconciliationFixtureFormat;
      currency: string;
      wrong_amount_mode?: ReconciliationFixtureWrongAmountMode;
      amount_delta?: number;
      payer_inn?: string;
      payer_name?: string;
      seed?: string;
    } = {
      scenario,
      invoice_id: invoiceId.trim(),
      org_id: orgIdValue,
      format,
      currency: currency.trim() || "RUB",
    };

    if (showWrongAmountSettings) {
      payload.wrong_amount_mode = wrongAmountMode;
      const parsedDelta = Number(amountDelta);
      if (Number.isFinite(parsedDelta) && parsedDelta >= 0) {
        payload.amount_delta = parsedDelta;
      }
    }

    if (payerInn.trim()) {
      payload.payer_inn = payerInn.trim();
    }
    if (payerName.trim()) {
      payload.payer_name = payerName.trim();
    }
    if (seed.trim()) {
      payload.seed = seed.trim();
    }

    setIsLoading(true);
    try {
      const response = await createFixtureBundle(payload);
      if (response.unavailable) {
        setNotAvailable(true);
        showToast("error", "Reconciliation API not available in this environment");
        return;
      }
      setBundle(response);
      setImportByFile({});
      showToast("success", "Fixture bundle generated");
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setUnauthorized(true);
        return;
      }
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  if (unauthorized) {
    return <div className="card error-state">Not authorized</div>;
  }

  const handleCreateImport = async (fileName: string, fileFormat: "CSV" | "CLIENT_BANK_1C" | "MT940") => {
    if (!bundle) return;
    const response = await createFixtureImport(bundle.bundle_id, { format: fileFormat, file_name: fileName });
    if (response.unavailable) {
      setNotAvailable(true);
      showToast("error", "Reconciliation API not available in this environment");
      return;
    }
    setImportByFile((prev) => ({ ...prev, [fileName]: response }));
    showToast("success", "Reconciliation import created");
  };

  const handleParseMatch = async (fileName: string) => {
    const importInfo = importByFile[fileName];
    if (!importInfo?.import_id || !importInfo.object_key) return;
    const response = await completeStatementImport(importInfo.import_id, { object_key: importInfo.object_key });
    if (response.unavailable) {
      setNotAvailable(true);
      showToast("error", "Reconciliation API not available in this environment");
      return;
    }
    showToast("success", "Parse & match completed");
  };

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>Reconciliation fixtures</h1>
            <p className="muted">Generate deterministic statement files for SCN-2 and SCN-3 checks.</p>
          </div>
        </div>
        <div className="filters" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label className="filter">
            Scenario
            <select value={scenario} onChange={(event) => setScenario(event.target.value as ReconciliationFixtureScenario)}>
              {scenarioOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Invoice ID
            <input type="text" value={invoiceId} onChange={(event) => setInvoiceId(event.target.value)} />
          </label>
          <label className="filter">
            Org ID
            <input type="number" value={orgId} onChange={(event) => setOrgId(event.target.value)} />
          </label>
          <label className="filter">
            Format
            <select value={format} onChange={(event) => setFormat(event.target.value as ReconciliationFixtureFormat)}>
              {formatOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="filter">
            Currency
            <input type="text" value={currency} onChange={(event) => setCurrency(event.target.value)} />
          </label>
          <label className="filter">
            Payer INN
            <input type="text" value={payerInn} onChange={(event) => setPayerInn(event.target.value)} />
          </label>
          <label className="filter">
            Payer name
            <input type="text" value={payerName} onChange={(event) => setPayerName(event.target.value)} />
          </label>
          <label className="filter">
            Seed
            <input type="text" value={seed} onChange={(event) => setSeed(event.target.value)} />
          </label>
          {showWrongAmountSettings ? (
            <>
              <label className="filter">
                Wrong amount mode
                <select
                  value={wrongAmountMode}
                  onChange={(event) =>
                    setWrongAmountMode(event.target.value as ReconciliationFixtureWrongAmountMode)
                  }
                >
                  {wrongAmountOptions.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="filter">
                Amount delta
                <input type="number" value={amountDelta} onChange={(event) => setAmountDelta(event.target.value)} />
              </label>
            </>
          ) : null}
        </div>
        <div className="stack-inline" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="neft-btn-secondary" onClick={handleGenerate} disabled={isLoading}>
            {isLoading ? "Generating..." : "Generate"}
          </button>
        </div>
      </section>

      {notAvailable ? <div className="card">Reconciliation API not available in this environment</div> : null}
      {error ? <div className="card error-state">{error}</div> : null}

      <section className="card">
        <h2 style={{ marginTop: 0 }}>Generated files</h2>
        {bundle?.files.length ? (
          <ul className="stack" style={{ paddingLeft: 18 }}>
            {bundle.files.map((file) => (
              <li key={file.file_name} className="stack-inline" style={{ gap: 12 }}>
                <span>{file.file_name}</span>
                <a className="ghost" href={file.download_url} target="_blank" rel="noreferrer">
                  Download
                </a>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => handleCreateImport(file.file_name, file.format)}
                >
                  Create import
                </button>
                {importByFile[file.file_name]?.import_id ? (
                  <>
                    <button type="button" className="ghost" onClick={() => handleParseMatch(file.file_name)}>
                      Parse & Match
                    </button>
                    <span className="muted">Import: {importByFile[file.file_name].import_id}</span>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No bundle generated yet.</p>
        )}
        <div className="muted" style={{ marginTop: 12 }}>
          <strong>Next steps:</strong>
          <ul>
            <li>Upload any of the files into Reconciliation Imports, or create an import from here.</li>
            <li>Run Parse/Match to verify the expected outcome.</li>
            <li>SCN-2 should stay unmatched or under review; SCN-3 should create an overpayment.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

export default ReconciliationFixturesPage;

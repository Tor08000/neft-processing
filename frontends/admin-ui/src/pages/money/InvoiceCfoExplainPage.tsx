import React, { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { cfoExplainInvoice, moneyExplain } from "../../api/moneyFlow";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type { MoneyExplainResponse } from "../../types/money";
import { formatError } from "../../utils/apiErrors";

export const InvoiceCfoExplainPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [data, setData] = useState<MoneyExplainResponse | null>(null);
  const [moneyData, setMoneyData] = useState<MoneyExplainResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!accessToken || !id) return;
    setLoading(true);
    const flowType = searchParams.get("flow_type") ?? "INVOICE_PAYMENT";
    const flowRefId = searchParams.get("flow_ref_id") ?? id;
    Promise.all([
      cfoExplainInvoice(accessToken, id),
      moneyExplain(accessToken, { flow_type: flowType, flow_ref_id: flowRefId }).catch(() => null),
    ])
      .then(([cfoResponse, moneyResponse]) => {
        setData(cfoResponse);
        setMoneyData(moneyResponse);
      })
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  }, [accessToken, id, searchParams, showToast]);

  const links = Array.isArray(data?.money_flow_links) ? (data?.money_flow_links as Record<string, unknown>[]) : [];
  const charges = Array.isArray(data?.charges) ? (data?.charges as Record<string, unknown>[]) : [];
  const segments = Array.isArray(data?.segments) ? (data?.segments as Record<string, unknown>[]) : [];

  const buildColumns = (rows: Record<string, unknown>[]): DataColumn<Record<string, unknown>>[] => {
    if (!rows.length) return [];
    return Object.keys(rows[0]).map((key) => ({ key, title: key }));
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <Toast toast={toast} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Invoice CFO Explain {id}</h1>
        <button type="button" onClick={() => navigate(`/billing/invoices/${id}`)}>
          Invoice details
        </button>
      </div>
      {!data && <div>No data</div>}
      {data && (
        <div style={{ display: "grid", gap: 16 }}>
          <div>
            <h3>Totals</h3>
            <JsonViewer value={data.totals ?? {}} />
          </div>
          <div>
            <h3>Segments</h3>
            <DataTable data={segments} columns={buildColumns(segments)} emptyMessage="Нет сегментов" />
          </div>
          <div>
            <h3>Charges</h3>
            <DataTable data={charges} columns={buildColumns(charges)} emptyMessage="Нет charges" />
          </div>
          <div>
            <h3>Ledger summary</h3>
            <JsonViewer value={data.ledger_summary ?? {}} />
          </div>
          <div>
            <h3>Money flow links</h3>
            <DataTable data={links} columns={buildColumns(links)} emptyMessage="Нет links" />
          </div>
          {moneyData && (
            <div>
              <h3>Money explain (v2)</h3>
              <JsonViewer value={moneyData} />
            </div>
          )}
          <details>
            <summary>Raw JSON</summary>
            <JsonViewer value={data} />
          </details>
        </div>
      )}
    </div>
  );
};

export default InvoiceCfoExplainPage;

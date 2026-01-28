import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchPayoutBatchDetails,
  fetchPayoutBatches,
  fetchPayoutExports,
  createPayoutExport,
  fetchPayoutExportFormats,
} from "../api/payouts";
import { Loader } from "../components/Loader/Loader";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { Table, type Column } from "../components/Table/Table";
import { formatAmount, formatDate } from "../utils/format";
import { PayoutBatchDetail, PayoutBatchSummary, PayoutExportFile } from "../types/payouts";
import { getStoredToken } from "../api/client";
import { ADMIN_API_BASE, normalizeAdminPath } from "../api/base";

export const PayoutBatchesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [batches, setBatches] = useState<PayoutBatchSummary[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [provider, setProvider] = useState("bank");
  const [externalRef, setExternalRef] = useState("");
  const [exportFormat, setExportFormat] = useState<"CSV" | "XLSX">("CSV");
  const [bankFormatCode, setBankFormatCode] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: batchesData, isFetching, isLoading, error, refetch } = useQuery({
    queryKey: ["payouts", "batches"],
    queryFn: () => fetchPayoutBatches({}),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) =>
      previousData ?? { items: [], total: 0, limit: 0, offset: 0 },
  });

  useEffect(() => {
    const items = batchesData?.items ?? [];
    setBatches(items);
    if (items.length && !selectedBatchId) {
      setSelectedBatchId(items[0].batch_id);
    }
    if (items.length && selectedBatchId && !items.find((b) => b.batch_id === selectedBatchId)) {
      setSelectedBatchId(items[0].batch_id);
    }
  }, [batchesData, selectedBatchId]);

  const { data: selectedBatchDetails, isFetching: isDetailsFetching } = useQuery({
    queryKey: ["payouts", selectedBatchId, "details"],
    queryFn: () => fetchPayoutBatchDetails(selectedBatchId!),
    enabled: Boolean(selectedBatchId),
    staleTime: 30_000,
  });

  const { data: exports = [], isFetching: isExportsFetching } = useQuery({
    queryKey: ["payouts", selectedBatchId, "exports"],
    queryFn: () => fetchPayoutExports(selectedBatchId!),
    enabled: Boolean(selectedBatchId),
    staleTime: 10_000,
  });

  const { data: exportFormats = [] } = useQuery({
    queryKey: ["payouts", "export-formats"],
    queryFn: () => fetchPayoutExportFormats(),
    staleTime: 60_000,
  });

  const exportMutation = useMutation({
    mutationFn: (format: "CSV" | "XLSX") => {
      if (!selectedBatchId) return Promise.reject(new Error("No batch selected"));
      return createPayoutExport(selectedBatchId, {
        format,
        provider: provider || undefined,
        external_ref: externalRef || undefined,
        bank_format_code: format === "XLSX" ? bankFormatCode || undefined : undefined,
      });
    },
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ["payouts", selectedBatchId, "exports"] });
    },
    onError: (err: Error) => {
      if (err.message.includes("external_ref_conflict")) {
        setErrorMessage("external_ref already used");
      } else if (err.message.includes("bank_format_required")) {
        setErrorMessage("Bank template is required for XLSX export");
      } else {
        setErrorMessage(err.message);
      }
    },
  });

  const selectedBatch = useMemo<PayoutBatchDetail | null>(() => {
    return selectedBatchDetails ?? null;
  }, [selectedBatchDetails]);

  const batchColumns: Column<PayoutBatchSummary>[] = [
    { key: "batch_id", title: "Batch ID", render: (row) => row.batch_id },
    { key: "total_amount", title: "Total amount", render: (row) => formatAmount(row.total_amount) },
    { key: "items_count", title: "Items", render: (row) => row.items_count },
    { key: "state", title: "State", render: (row) => <StatusBadge status={row.state} /> },
  ];

  const exportColumns: Column<PayoutExportFile>[] = [
    { key: "format", title: "Format", render: (row) => row.format },
    { key: "bank_format_code", title: "Bank template", render: (row) => row.bank_format_code || "-" },
    { key: "state", title: "State", render: (row) => <StatusBadge status={row.state} /> },
    { key: "provider", title: "Provider", render: (row) => row.provider || "-" },
    { key: "external_ref", title: "External ref", render: (row) => row.external_ref || "-" },
    {
      key: "download",
      title: "Download",
      render: (row) => (
        <button onClick={() => handleDownload(row)} style={{ padding: "6px 10px" }}>
          Download
        </button>
      ),
    },
  ];

  const handleDownload = async (exportFile: PayoutExportFile) => {
    try {
      const token = getStoredToken();
      const base = ADMIN_API_BASE.replace(/\/+$/, "");
      const normalizedDownloadPath = normalizeAdminPath(exportFile.download_url);
      const downloadUrl = exportFile.download_url.startsWith("http")
        ? exportFile.download_url
        : `${base}${normalizedDownloadPath}`;
      const response = await fetch(downloadUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `payout_export_${exportFile.export_id}.${exportFile.format.toLowerCase()}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Download failed";
      setErrorMessage(message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Payout batches</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => refetch()} disabled={isFetching}>
            Refresh
          </button>
          {(isLoading || isFetching || isDetailsFetching || isExportsFetching) && <Loader label="Синхронизация" />}
          {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
        </div>
      </div>

      <div className="card-grid" style={{ gridTemplateColumns: "2fr 1fr" }}>
        <div>
          <h2>Batches</h2>
          <Table columns={batchColumns} data={batches} onRowClick={(row) => setSelectedBatchId(row.batch_id)} />
        </div>
        <div>
          <h2>Batch details</h2>
          {selectedBatch ? (
            <div className="card" style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <div>
                  <div style={{ fontWeight: 700 }}>{selectedBatch.partner_id}</div>
                  <div style={{ color: "#475569" }}>
                    {formatDate(selectedBatch.date_from)} → {formatDate(selectedBatch.date_to)}
                  </div>
                </div>
                <StatusBadge status={selectedBatch.state} />
              </div>
              <p style={{ marginBottom: 4 }}>Total amount: {formatAmount(selectedBatch.total_amount)}</p>
              <p style={{ marginBottom: 12 }}>Operations: {selectedBatch.operations_count}</p>

              <div className="card" style={{ background: "#f8fafc", marginBottom: 12 }}>
                <h3 style={{ marginTop: 0 }}>Registry / Export</h3>
                <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
                  <label>
                    Format
                    <select
                      value={exportFormat}
                      onChange={(e) => {
                        const next = e.target.value as "CSV" | "XLSX";
                        setExportFormat(next);
                        if (next === "CSV") {
                          setBankFormatCode("");
                        }
                      }}
                    >
                      <option value="CSV">CSV</option>
                      <option value="XLSX">XLSX</option>
                    </select>
                  </label>
                  {exportFormat === "XLSX" && (
                    <label>
                      Bank template
                      <select
                        value={bankFormatCode}
                        onChange={(e) => setBankFormatCode(e.target.value)}
                      >
                        <option value="">Select template</option>
                        {exportFormats.map((format) => (
                          <option key={format.code} value={format.code}>
                            {format.title}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label>
                    Provider
                    <input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="bank" />
                  </label>
                  <label>
                    External ref
                    <input value={externalRef} onChange={(e) => setExternalRef(e.target.value)} placeholder="BANK-REG-001" />
                  </label>
                </div>
                <div className="actions">
                  <button
                    onClick={() => exportMutation.mutate(exportFormat)}
                    disabled={
                      exportMutation.isPending || (exportFormat === "XLSX" && !bankFormatCode)
                    }
                  >
                    Generate {exportFormat}
                  </button>
                  {exportFormat === "XLSX" && !bankFormatCode && (
                    <span style={{ color: "#64748b", fontSize: 12 }}>Select a bank template to continue.</span>
                  )}
                </div>
                {errorMessage && <p style={{ color: "#dc2626", marginTop: 8 }}>{errorMessage}</p>}
              </div>

              <h3>Exports</h3>
              <Table columns={exportColumns} data={exports} />
            </div>
          ) : (
            <p>Select batch to view details</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default PayoutBatchesPage;

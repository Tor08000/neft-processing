export type ClearingStatus = "PENDING" | "SENT" | "CONFIRMED" | "FAILED";

export interface ClearingBatch {
  id: string;
  merchant_id: string;
  batch_date: string;
  currency: string;
  total_amount: number;
  status: ClearingStatus;
  operations_count?: number;
  created_at?: string;
  updated_at?: string;
  operations?: ClearingBatchOperation[] | null;
}

export interface ClearingBatchDetails {
  batch: ClearingBatch;
  operations: ClearingBatchOperation[];
}

export interface ClearingBatchOperation {
  id: string;
  batch_id: string;
  operation_id: string;
  amount: number;
}

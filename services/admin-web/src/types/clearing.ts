export type ClearingStatus = "PENDING" | "SENT" | "CONFIRMED" | "FAILED";

export interface ClearingBatch {
  id: string;
  merchant_id: string;
  date_from: string;
  date_to: string;
  total_amount: number;
  operations_count: number;
  status: ClearingStatus;
  created_at: string;
  updated_at: string;
}

export interface ClearingBatchOperation {
  id: string;
  batch_id: string;
  operation_id: string;
  amount: number;
}

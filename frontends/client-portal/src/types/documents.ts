export interface ClientDocumentSummary {
  id: string;
  document_type: string;
  status: string;
  period_from: string;
  period_to: string;
  version: number;
  number?: string | null;
  created_at: string;
  pdf_hash?: string | null;
}

export interface ClientDocumentList {
  items: ClientDocumentSummary[];
  total: number;
  limit: number;
  offset: number;
}

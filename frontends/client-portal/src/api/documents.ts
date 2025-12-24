import { request } from "./http";
import type { AuthSession } from "./types";
import type { DocumentAcknowledgement } from "../types/invoices";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function acknowledgeDocument(
  documentType: string,
  documentId: string,
  user: AuthSession | null,
): Promise<DocumentAcknowledgement> {
  return request<DocumentAcknowledgement>(
    `/documents/${documentType}/${documentId}/ack`,
    {
      method: "POST",
    },
    withToken(user),
  );
}

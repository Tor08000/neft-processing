export interface CardLimit {
  type: string;
  value: number;
  window: string;
}

export interface ClientCard {
  id: string;
  pan_masked?: string | null;
  status: string;
  limits: CardLimit[];
  last_operation_id?: string;
  last_operation_amount?: number;
}

export interface ClientCardsResponse {
  items: ClientCard[];
}

export interface BalanceItem {
  currency: string;
  current: number | string;
  available: number | string;
}

export interface BalancesResponse {
  items: BalanceItem[];
}

export interface Statement {
  currency: string;
  start_balance: number | string;
  end_balance: number | string;
  credits: number | string;
  debits: number | string;
}

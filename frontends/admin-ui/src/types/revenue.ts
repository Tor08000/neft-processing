export type MoneyAmount = {
  amount: number;
  currency: string;
};

export type RevenuePlanMixItem = {
  plan: string;
  orgs: number;
  mrr: number | null;
};

export type RevenueAddonMixItem = {
  addon: string;
  orgs: number;
  mrr: number;
};

export type RevenueSummaryResponse = {
  as_of: string;
  mrr: MoneyAmount;
  arr: MoneyAmount;
  active_orgs: number;
  overdue_orgs: number;
  overdue_amount: number;
  usage_revenue_mtd: number;
  plan_mix: RevenuePlanMixItem[];
  addon_mix: RevenueAddonMixItem[];
  overdue_buckets: RevenueOverdueBucket[];
};

export type RevenueOverdueBucket = {
  bucket: string;
  label: string;
  orgs: number;
  amount: number;
};

export type RevenueOverdueItem = {
  org_id: number;
  org_name: string | null;
  invoice_id: string;
  due_at: string | null;
  overdue_days: number;
  amount: number;
  currency: string | null;
  subscription_plan: string | null;
  subscription_status: string | null;
};

export type RevenueOverdueResponse = {
  items: RevenueOverdueItem[];
  total: number;
  limit: number;
  offset: number;
};

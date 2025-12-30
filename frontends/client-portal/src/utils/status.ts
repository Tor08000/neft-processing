import { translate } from "../i18n";

const resolveStatusLabel = (group: "orders" | "documents", value?: string | null): string => {
  if (!value) return translate("common.notAvailable");
  const key = `statuses.${group}.${value}`;
  const label = translate(key);
  return label === key ? value : label;
};

export const getOrderStatusLabel = (value?: string | null): string => resolveStatusLabel("orders", value);
export const getMarketplaceDocumentStatusLabel = (value?: string | null): string => resolveStatusLabel("documents", value);

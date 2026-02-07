import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const cyrillicPattern = /["'`][^"'`]*[А-Яа-яЁё][^"'`]*["'`]/;
const forbiddenDemoPattern = /(forbidden|\[object Object\]|ordersPage\\.|servicesCatalogPage\\.)/i;

const files = [
  "../pages/PricesPage.tsx",
  "../pages/IntegrationsPage.tsx",
  "../pages/services/ServicesCatalogPageProd.tsx",
  "../pages/orders/OrdersPageProd.tsx",
].map((file) => path.join(__dirname, file));

const demoFiles = [
  "../pages/documents/DocumentsPageDemo.tsx",
  "../pages/finance/FinancePageDemo.tsx",
  "../pages/payouts/PayoutsPageDemo.tsx",
  "../pages/analytics/AnalyticsPageDemo.tsx",
].map((file) => path.join(__dirname, file));

describe("i18n key pages", () => {
  it("avoids hardcoded cyrillic strings in key pages", () => {
    for (const file of files) {
      const contents = readFileSync(file, "utf8");
      expect(contents).not.toMatch(cyrillicPattern);
    }
  });

  it("avoids forbidden strings in demo pages", () => {
    for (const file of demoFiles) {
      const contents = readFileSync(file, "utf8");
      expect(contents).not.toMatch(forbiddenDemoPattern);
    }
  });
});

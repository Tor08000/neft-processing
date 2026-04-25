import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const cyrillicPattern = /["'`][^"'`]*[А-Яа-яЁё][^"'`]*["'`]/;

const files = [
  "../pages/MarketplaceCatalogPage.tsx",
  "../pages/MarketplaceOrdersPage.tsx",
  "../pages/ClientDocumentsPage.tsx",
  "../pages/FinanceExportsPage.tsx",
  "../components/AccessGate.tsx",
  "../components/DemoEmptyState.tsx",
].map((file) => path.join(__dirname, file));

describe("i18n key pages", () => {
  it("avoids hardcoded cyrillic strings in key pages", () => {
    for (const file of files) {
      const contents = readFileSync(file, "utf8");
      expect(contents).not.toMatch(cyrillicPattern);
    }
  });
});

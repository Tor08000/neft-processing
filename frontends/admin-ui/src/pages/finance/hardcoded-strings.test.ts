import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const cyrillicPattern = /["'`][^"'`]*[А-Яа-яЁё][^"'`]*["'`]/;

const files = [
  "./FinanceOverviewPage.tsx",
  "./PaymentIntakesPage.tsx",
  "./PayoutQueuePage.tsx",
  "./InvoiceDetailsPage.tsx",
  "./PayoutDetailsPage.tsx",
  "./RevenuePage.tsx",
  "./PayoutBatchDetail.tsx",
].map((file) => path.join(__dirname, file));

describe("finance key page copy", () => {
  it("avoids hardcoded cyrillic strings in sentinel-covered finance pages", () => {
    for (const file of files) {
      const contents = readFileSync(file, "utf8");
      expect(contents).not.toMatch(cyrillicPattern);
    }
  });
});

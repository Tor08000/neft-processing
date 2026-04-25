import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const cyrillicPattern = /["'`][^"'`]*[А-Яа-яЁё][^"'`]*["'`]/;

const files = ["./MarketplaceModerationPage.tsx", "./MarketplaceModerationDetailPage.tsx"].map((file) =>
  path.join(__dirname, file),
);

describe("marketplace moderation key page copy", () => {
  it("avoids hardcoded cyrillic strings in sentinel-covered marketplace moderation pages", () => {
    for (const file of files) {
      const contents = readFileSync(file, "utf8");
      expect(contents).not.toMatch(cyrillicPattern);
    }
  });
});

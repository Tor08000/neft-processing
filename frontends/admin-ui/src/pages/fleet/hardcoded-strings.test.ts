import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const cyrillicPattern = /["'`][^"'`]*[А-Яа-яЁё][^"'`]*["'`]/;

const files = [
  "./FleetCardsPage.tsx",
  "./FleetGroupsPage.tsx",
  "./FleetEmployeesPage.tsx",
  "./FleetLimitsPage.tsx",
  "./FleetSpendPage.tsx",
].map((file) => path.join(__dirname, file));

describe("fleet key page copy", () => {
  it("avoids hardcoded cyrillic strings in sentinel-covered fleet pages", () => {
    for (const file of files) {
      const contents = readFileSync(file, "utf8");
      expect(contents).not.toMatch(cyrillicPattern);
    }
  });
});

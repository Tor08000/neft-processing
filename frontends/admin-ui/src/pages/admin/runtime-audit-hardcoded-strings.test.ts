import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const cyrillicPattern = /["'`][^"'`]*[А-Яа-яЁё][^"'`]*["'`]/;

const files = [
  "./RuntimeCenterPage.tsx",
  "./AuditPage.tsx",
].map((file) => path.join(__dirname, file));

describe("admin runtime and audit copy", () => {
  it("avoids hardcoded cyrillic strings in sentinel-covered runtime and audit pages", () => {
    for (const file of files) {
      const contents = readFileSync(file, "utf8");
      expect(contents).not.toMatch(cyrillicPattern);
    }
  });
});

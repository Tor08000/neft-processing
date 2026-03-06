import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("Partner LoginPage demo credentials", () => {
  test("keeps canonical demo password in UI", () => {
    const source = readFileSync(resolve(__dirname, "./LoginPage.tsx"), "utf-8");

    expect(source).toContain('useState("Partner123!")');
    expect(source).toContain('value="Partner123!"');
    expect(source).toContain('placeholder="Partner123!"');
  });
});

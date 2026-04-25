import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("Partner LoginPage demo credentials", () => {
  test("gates canonical demo password behind explicit demo mode", () => {
    const source = readFileSync(resolve(__dirname, "./LoginPage.tsx"), "utf-8");

    expect(source).toContain('import.meta.env.VITE_DEMO_MODE === "true"');
    expect(source).toContain('const demoPassword = "Partner123!"');
    expect(source).not.toContain('useState("Partner123!")');
    expect(source).not.toContain('value="Partner123!"');
    expect(source).not.toContain('placeholder="Partner123!"');
  });
});

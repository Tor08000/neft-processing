import "@testing-library/jest-dom";
import { beforeEach, vi } from "vitest";

const fixedNow = new Date("2024-01-01T00:00:00.000Z");

beforeEach(() => {
  vi.spyOn(Date, "now").mockReturnValue(fixedNow.getTime());
  vi.stubGlobal("crypto", {
    randomUUID: () => "test-uuid-0000-0000-0000-000000000000",
  });
  vi.stubEnv("VITE_API_BASE_URL", "/api");
  vi.stubEnv("VITE_DEMO_MODE", "true");
});

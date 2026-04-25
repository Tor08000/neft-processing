import "@testing-library/jest-dom";
import { beforeEach, vi } from "vitest";

const fixedNow = new Date("2024-01-01T00:00:00.000Z");
const originalConsoleWarn = console.warn.bind(console);
const filteredConsoleWarn: typeof console.warn = (...args) => {
  const message = String(args[0] ?? "");
  if (message.includes("React Router Future Flag Warning")) return;
  originalConsoleWarn(...args);
};

console.warn = filteredConsoleWarn;

beforeEach(() => {
  vi.spyOn(Date, "now").mockReturnValue(fixedNow.getTime());
  vi.stubGlobal("crypto", {
    randomUUID: () => "test-uuid-0000-0000-0000-000000000000",
  });
  vi.stubEnv("VITE_API_BASE_URL", "/api");
  vi.stubEnv("VITE_DEMO_MODE", "false");
});

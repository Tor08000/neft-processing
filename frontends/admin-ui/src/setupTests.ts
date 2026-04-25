import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

const originalConsoleWarn = console.warn.bind(console);
const filteredConsoleWarn: typeof console.warn = (...args) => {
  const message = String(args[0] ?? "");
  if (message.includes("React Router Future Flag Warning")) return;
  originalConsoleWarn(...args);
};

console.warn = filteredConsoleWarn;

beforeEach(() => {
  window.localStorage.clear();
});

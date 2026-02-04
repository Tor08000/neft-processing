export type ClientTheme = "light" | "dark";

const STORAGE_KEY = "neft.client.theme";

export function getInitialTheme(): ClientTheme {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "light" || saved === "dark") return saved;

  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
  return prefersDark ? "dark" : "light";
}

export function applyTheme(theme: ClientTheme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(STORAGE_KEY, theme);
}

export function toggleTheme(): ClientTheme {
  const current = (document.documentElement.dataset.theme as ClientTheme) || "light";
  const next: ClientTheme = current === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}

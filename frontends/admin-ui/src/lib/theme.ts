export type NeftTheme = "light" | "dark";

const STORAGE_KEY = "neft.theme";

export function getInitialTheme(): NeftTheme {
  const saved = localStorage.getItem(STORAGE_KEY) as NeftTheme | null;
  if (saved === "light" || saved === "dark") return saved;

  return "dark";
}

export function applyTheme(theme: NeftTheme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(STORAGE_KEY, theme);
}

export function toggleTheme(current: NeftTheme): NeftTheme {
  const next: NeftTheme = current === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}

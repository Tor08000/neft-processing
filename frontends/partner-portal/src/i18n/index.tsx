import type { ReactNode } from "react";
import { createContext, useContext, useMemo } from "react";
import ru from "./ru.json";
import en from "./en.json";

export type Locale = "ru" | "en";

type Translations = Record<string, string | Translations>;

const translations: Record<Locale, Translations> = { ru, en };
const fallbackLocale: Locale = "en";

const resolveLocale = (value?: string): Locale => {
  if (value === "en") return "en";
  return "ru";
};

let activeLocale: Locale = resolveLocale(import.meta.env.VITE_LOCALE);

const lookup = (locale: Locale, key: string): string | undefined => {
  const parts = key.split(".");
  let current: string | Translations | undefined = translations[locale];
  for (const part of parts) {
    if (!current || typeof current !== "object") return undefined;
    current = current[part];
  }
  return typeof current === "string" ? current : undefined;
};

const interpolate = (value: string, vars?: Record<string, string | number>): string => {
  if (!vars) return value;
  return Object.entries(vars).reduce((acc, [key, replacement]) => acc.replaceAll(`{${key}}`, String(replacement)), value);
};

export const translate = (key: string, vars?: Record<string, string | number>, locale: Locale = activeLocale): string => {
  const value = lookup(locale, key) ?? lookup(fallbackLocale, key);
  if (!value) return key;
  return interpolate(value, vars);
};

type I18nContextValue = {
  locale: Locale;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nContextValue>({
  locale: activeLocale,
  t: (key, vars) => translate(key, vars),
});

export function I18nProvider({ children, locale }: { children: ReactNode; locale?: Locale }) {
  const resolved = useMemo(() => resolveLocale(locale ?? import.meta.env.VITE_LOCALE), [locale]);
  activeLocale = resolved;
  const value = useMemo<I18nContextValue>(
    () => ({
      locale: resolved,
      t: (key, vars) => translate(key, vars, resolved),
    }),
    [resolved],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export const useI18n = () => useContext(I18nContext);

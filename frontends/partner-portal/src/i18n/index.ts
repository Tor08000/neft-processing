import type { ReactNode } from "react";
import { useEffect } from "react";
import i18n from "i18next";
import { I18nextProvider, initReactI18next, useTranslation } from "react-i18next";
import ru from "./ru.json";
import en from "./en.json";

export type Locale = "ru" | "en";

const resolveLocale = (value?: string): Locale => {
  if (value === "en") return "en";
  return "ru";
};

i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
    en: { translation: en },
  },
  lng: resolveLocale(import.meta.env.VITE_LOCALE),
  fallbackLng: "ru",
  defaultNS: "translation",
  interpolation: { escapeValue: false },
});

export const translate = (
  key: string,
  vars?: Record<string, string | number>,
  locale: Locale = resolveLocale(i18n.language),
): string => i18n.t(key, { ...vars, lng: locale });

export function I18nProvider({ children, locale }: { children: ReactNode; locale?: Locale }) {
  const resolved = resolveLocale(locale ?? import.meta.env.VITE_LOCALE);

  useEffect(() => {
    if (i18n.language !== resolved) {
      void i18n.changeLanguage(resolved);
    }
  }, [resolved]);

  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>;
}

export const useI18n = () => {
  const { t, i18n: instance } = useTranslation();
  return { locale: resolveLocale(instance.language), t };
};

export default i18n;

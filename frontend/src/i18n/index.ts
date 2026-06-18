import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import zh from "./locales/zh.json";

export const LOCALE_STORAGE_KEY = "bugis_locale";
export const TIMEZONE_STORAGE_KEY = "bugis_timezone";
export const DEFAULT_LOCALE = "zh";
export const DEFAULT_TIMEZONE = "Asia/Shanghai";

const savedLocale =
  (typeof localStorage !== "undefined" && localStorage.getItem(LOCALE_STORAGE_KEY)) ||
  DEFAULT_LOCALE;

void i18n.use(initReactI18next).init({
  resources: {
    zh: { translation: zh },
    en: { translation: en },
  },
  lng: savedLocale,
  fallbackLng: DEFAULT_LOCALE,
  interpolation: { escapeValue: false },
});

export default i18n;

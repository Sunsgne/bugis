import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import i18n, {
  DEFAULT_LOCALE,
  DEFAULT_TIMEZONE,
  LOCALE_STORAGE_KEY,
  TIMEZONE_STORAGE_KEY,
} from "../i18n";
import { useAuth } from "../auth";
import { applyDayjsLocale, setActiveTimezone } from "../utils/datetime";

type LocaleCode = "zh" | "en";

interface LocaleCtx {
  locale: LocaleCode;
  timezone: string;
  setLocale: (code: LocaleCode, persist?: boolean) => Promise<void>;
  setTimezone: (tz: string, persist?: boolean) => Promise<void>;
  savePreferences: (prefs: { locale?: LocaleCode; timezone?: string }) => Promise<void>;
}

const Ctx = createContext<LocaleCtx | null>(null);

function normalizeLocale(value?: string | null): LocaleCode {
  return value === "en" ? "en" : "zh";
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const { user, refreshUser } = useAuth();
  const { i18n: i18nInstance } = useTranslation();
  const [locale, setLocaleState] = useState<LocaleCode>(() =>
    normalizeLocale(localStorage.getItem(LOCALE_STORAGE_KEY) || DEFAULT_LOCALE),
  );
  const [timezone, setTimezoneState] = useState(
    () => localStorage.getItem(TIMEZONE_STORAGE_KEY) || DEFAULT_TIMEZONE,
  );

  const applyLocal = useCallback((nextLocale: LocaleCode, nextTz: string) => {
    setLocaleState(nextLocale);
    setTimezoneState(nextTz);
    localStorage.setItem(LOCALE_STORAGE_KEY, nextLocale);
    localStorage.setItem(TIMEZONE_STORAGE_KEY, nextTz);
    void i18nInstance.changeLanguage(nextLocale);
    applyDayjsLocale(nextLocale);
    setActiveTimezone(nextTz);
    document.documentElement.lang = nextLocale === "zh" ? "zh-CN" : "en";
  }, [i18nInstance]);

  useEffect(() => {
    if (!user) return;
    applyLocal(normalizeLocale(user.locale), user.timezone || DEFAULT_TIMEZONE);
  }, [user?.id, user?.locale, user?.timezone, applyLocal, user]);

  const persist = useCallback(
    async (patch: { locale?: LocaleCode; timezone?: string }) => {
      if (!user) {
        if (patch.locale) applyLocal(patch.locale, patch.timezone ?? timezone);
        if (patch.timezone) applyLocal(locale, patch.timezone);
        return;
      }
      const { data } = await api.patch("/auth/profile", patch);
      applyLocal(normalizeLocale(data.locale), data.timezone || DEFAULT_TIMEZONE);
      await refreshUser();
    },
    [user, applyLocal, timezone, locale, refreshUser],
  );

  const value = useMemo<LocaleCtx>(
    () => ({
      locale,
      timezone,
      setLocale: async (code, doPersist = true) => {
        if (doPersist) await persist({ locale: code });
        else applyLocal(code, timezone);
      },
      setTimezone: async (tz, doPersist = true) => {
        if (doPersist) await persist({ timezone: tz });
        else applyLocal(locale, tz);
      },
      savePreferences: persist,
    }),
    [locale, timezone, persist, applyLocal],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLocale() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}

/** Apply saved guest preferences before login. */
export function bootstrapLocaleFromStorage() {
  const loc = normalizeLocale(localStorage.getItem(LOCALE_STORAGE_KEY));
  const tz = localStorage.getItem(TIMEZONE_STORAGE_KEY) || DEFAULT_TIMEZONE;
  void i18n.changeLanguage(loc);
  applyDayjsLocale(loc);
  setActiveTimezone(tz);
  document.documentElement.lang = loc === "zh" ? "zh-CN" : "en";
}

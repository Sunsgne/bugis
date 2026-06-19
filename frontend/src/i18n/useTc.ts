import { useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import en from "./locales/en.json";
import zh from "./locales/zh.json";

type Nested = Record<string, unknown>;

function flattenStrings(obj: Nested, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "string") out[key] = v;
    else if (v && typeof v === "object") Object.assign(out, flattenStrings(v as Nested, key));
  }
  return out;
}

const ZH_FLAT = flattenStrings(zh as Nested);
const EN_FLAT = flattenStrings(en as Nested);

/** Chinese literal → English (built from locale files). */
const ZH_TO_EN: Record<string, string> = {};
for (const [key, zhVal] of Object.entries(ZH_FLAT)) {
  const enVal = EN_FLAT[key];
  if (enVal && zhVal && enVal !== zhVal) ZH_TO_EN[zhVal] = enVal;
}

/**
 * useTc — translate hardcoded Chinese UI copy.
 * tc("状态") → "Status" when locale is en; returns original in zh mode.
 */
export function useTc() {
  const { t, i18n } = useTranslation();
  const isEn = i18n.language === "en" || i18n.language.startsWith("en-");

  const tc = useCallback(
    (zhText: string): string => {
      if (!zhText) return zhText;
      if (!isEn) return zhText;
      return ZH_TO_EN[zhText] ?? t(`auto:${zhText}`, { defaultValue: zhText });
    },
    [isEn, t],
  );

  const values = useMemo(
    () => ({
      brand: {
        product: tc("Bugis Network") || "Bugis Network",
        tagline: tc(ZH_FLAT["brand.tagline"] || ""),
        heroTitle: tc(ZH_FLAT["brand.heroTitle"] || ""),
        heroSubtitle: tc(ZH_FLAT["brand.heroSubtitle"] || ""),
      },
      action: {
        save: t("action.save"),
        cancel: t("action.cancel"),
        create: t("action.create"),
        createCircuit: t("action.createCircuit"),
        edit: t("action.edit"),
        delete: t("action.delete"),
        export: t("action.export"),
        import: t("action.import"),
        refresh: t("action.refresh"),
        login: t("action.login"),
        logout: t("action.logout"),
        confirm: t("action.confirm"),
        ack: t("action.ack"),
        changePassword: t("action.changePassword"),
      },
      empty: {
        default: t("empty.default"),
        circuits: t("empty.circuits"),
        devices: t("empty.devices"),
        snapshots: t("empty.snapshots"),
        traffic: t("empty.traffic"),
        alarms: t("empty.alarms"),
        data: t("empty.data"),
        selectDevice: t("empty.selectDevice"),
        noLearn: t("empty.noLearn"),
      },
      toast: {
        saved: t("toast.saved"),
        deleted: t("toast.deleted"),
        created: t("toast.created"),
        failed: t("toast.failed"),
        loginOk: t("toast.loginOk"),
        loginFail: t("toast.loginFail"),
      },
      page: {
        dashboard: t("page.dashboard"),
        tenants: t("page.tenants"),
        sites: t("page.sites"),
        devices: t("page.devices"),
        circuits: t("page.circuits"),
        circuitsFull: t("page.circuitsFull"),
        workOrders: t("page.workOrders"),
        config: t("page.config"),
        controllers: t("page.controllers"),
        controlPlane: t("page.controlPlane"),
        topology: t("page.topology"),
        capacity: t("page.capacity"),
        monitoring: t("page.monitoring"),
        alarms: t("page.alarms"),
        settings: t("page.settings"),
        audit: t("page.audit"),
        users: t("page.users"),
        notifications: t("page.notifications"),
        integrations: t("page.integrations"),
      },
    }),
    [t, tc, isEn],
  );

  return { t, tc, i18n, isEn, ...values };
}

import i18n from "./index";

/** Non-React: translate Chinese to current locale. */
export function tcStatic(zhText: string, lng?: string): string {
  const lang = lng ?? i18n.language ?? "zh";
  const isEn = lang.startsWith("en");
  if (!isEn) return zhText;
  return ZH_TO_EN[zhText] ?? zhText;
}

export { ZH_TO_EN };

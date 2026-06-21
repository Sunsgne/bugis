import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";
import "dayjs/locale/zh-cn";
import "dayjs/locale/en";
import { DEFAULT_TIMEZONE } from "../i18n";

dayjs.extend(utc);
dayjs.extend(timezone);

let activeTimezone = DEFAULT_TIMEZONE;

export function setActiveTimezone(tz: string) {
  activeTimezone = tz || DEFAULT_TIMEZONE;
}

export function getActiveTimezone() {
  return activeTimezone;
}

export function applyDayjsLocale(locale: string) {
  dayjs.locale(locale === "zh" ? "zh-cn" : "en");
}

export function parseApiDatetime(iso: string | undefined, tz?: string) {
  if (!iso) return dayjs(NaN);
  const zone = tz ?? activeTimezone;
  const trimmed = iso.trim();
  const normalized = trimmed.includes("T") ? trimmed : trimmed.replace(" ", "T");
  const hasOffset = /(?:[zZ]|[+-]\d{2}(?::?\d{2})?)$/.test(normalized);
  const parsed = hasOffset ? dayjs(normalized) : dayjs.utc(normalized);
  return parsed.tz(zone);
}

export function formatUserDate(
  iso: string | undefined,
  pattern: string,
  tz?: string,
): string {
  if (!iso) return "";
  const d = parseApiDatetime(iso, tz);
  return d.isValid() ? d.format(pattern) : "";
}

export function formatUserDateTime(iso: string | undefined, tz?: string) {
  return formatUserDate(iso, "YYYY-MM-DD HH:mm:ss", tz);
}

export function formatUserTimeLabel(iso: string | undefined, spanHours: number, tz?: string) {
  if (!iso) return "";
  const d = parseApiDatetime(iso, tz);
  if (!d.isValid()) return "";
  if (spanHours <= 1) return d.format("HH:mm");
  return d.format("MM-DD HH:mm");
}

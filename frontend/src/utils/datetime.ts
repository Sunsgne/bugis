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

export function formatUserDate(
  iso: string | undefined,
  pattern: string,
  tz?: string,
): string {
  if (!iso) return "";
  return dayjs(iso).tz(tz ?? activeTimezone).format(pattern);
}

export function formatUserTimeLabel(iso: string | undefined, spanHours: number, tz?: string) {
  if (!iso) return "";
  const zone = tz ?? activeTimezone;
  if (spanHours <= 1) return dayjs(iso).tz(zone).format("HH:mm");
  return dayjs(iso).tz(zone).format("MM-DD HH:mm");
}

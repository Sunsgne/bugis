import { useCallback, useMemo } from "react";
import dayjs, { type Dayjs } from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";
import "dayjs/locale/zh-cn";
import "dayjs/locale/en";
import { DEFAULT_TIMEZONE } from "../i18n";
import { useLocale } from "../context/LocaleContext";

dayjs.extend(utc);
dayjs.extend(timezone);

let activeTimezone = DEFAULT_TIMEZONE;

export function setActiveTimezone(tz: string) {
  activeTimezone = tz || DEFAULT_TIMEZONE;
  try {
    dayjs.tz.setDefault(activeTimezone);
  } catch {
    /* ignore invalid tz during bootstrap */
  }
}

export function getActiveTimezone() {
  return activeTimezone;
}

export function applyDayjsLocale(locale: string) {
  dayjs.locale(locale === "zh" ? "zh-cn" : "en");
}

/** Parse ISO / Date in the user's active timezone. */
export function userDayjs(iso?: string | Date | Dayjs | null, tz?: string): Dayjs {
  const zone = tz ?? activeTimezone;
  if (!iso) return dayjs().tz(zone);
  return dayjs(iso).tz(zone);
}

export function userNow(tz?: string): Dayjs {
  return dayjs().tz(tz ?? activeTimezone);
}

export function formatUserDate(
  iso: string | undefined | null,
  pattern: string,
  tz?: string,
): string {
  if (!iso) return "";
  return userDayjs(iso, tz).format(pattern);
}

export function formatUserTimeLabel(
  iso: string | undefined | null,
  spanHours: number,
  tz?: string,
): string {
  if (!iso) return "";
  const zone = tz ?? activeTimezone;
  if (spanHours <= 1) return userDayjs(iso, zone).format("HH:mm");
  if (spanHours <= 24) return userDayjs(iso, zone).format("MM-DD HH:mm");
  return userDayjs(iso, zone).format("YYYY-MM-DD HH:mm");
}

export function formatUserShort(iso?: string | null, tz?: string): string {
  return formatUserDate(iso, "MM-DD HH:mm", tz) || "—";
}

export function formatUserFull(iso?: string | null, tz?: string): string {
  return formatUserDate(iso, "MM-DD HH:mm:ss", tz) || "—";
}

export function formatUserLong(iso?: string | null, tz?: string): string {
  return formatUserDate(iso, "YYYY-MM-DD HH:mm:ss", tz) || "—";
}

export function formatUserDateTime(iso?: string | null, tz?: string): string {
  return formatUserDate(iso, "YYYY-MM-DD HH:mm", tz) || "—";
}

/** Map telemetry/chart points to user-timezone axis labels. */
export function mapTrafficSeriesLabels<T extends Record<string, unknown>>(
  points: T[],
  spanHours: number,
  xKey = "t",
  tz?: string,
): T[] {
  const zone = tz ?? activeTimezone;
  return points.map((p) => {
    const raw = p.bucket ?? p.ts ?? p.created_at;
    if (raw) {
      return { ...p, [xKey]: formatUserTimeLabel(String(raw), spanHours, zone) };
    }
    return p;
  });
}

export function formatCustomRangeLabel(
  start: Dayjs,
  end: Dayjs,
  tz?: string,
): string {
  const zone = tz ?? activeTimezone;
  return `${start.tz(zone).format("MM-DD HH:mm")} ~ ${end.tz(zone).format("MM-DD HH:mm")}`;
}

export function workOrderDatePresets(tz?: string) {
  const now = userNow(tz);
  return [
    { label: "今天", value: [now.startOf("day"), now.endOf("day")] as [Dayjs, Dayjs] },
    {
      label: "近 7 天",
      value: [now.subtract(6, "day").startOf("day"), now.endOf("day")] as [Dayjs, Dayjs],
    },
    {
      label: "近 30 天",
      value: [now.subtract(29, "day").startOf("day"), now.endOf("day")] as [Dayjs, Dayjs],
    },
    { label: "本月", value: [now.startOf("month"), now.endOf("month")] as [Dayjs, Dayjs] },
    { label: "本年", value: [now.startOf("year"), now.endOf("year")] as [Dayjs, Dayjs] },
  ];
}

/** Hook — subscribe to timezone changes and get bound formatters. */
export function useUserDatetime() {
  const { timezone, locale } = useLocale();

  const format = useCallback(
    (iso: string | undefined | null, pattern: string) => formatUserDate(iso, pattern, timezone),
    [timezone],
  );

  return useMemo(
    () => ({
      timezone,
      locale,
      userNow: () => userNow(timezone),
      userDayjs: (iso?: string | Date | Dayjs | null) => userDayjs(iso, timezone),
      format,
      formatShort: (iso?: string | null) => formatUserShort(iso, timezone),
      formatFull: (iso?: string | null) => formatUserFull(iso, timezone),
      formatLong: (iso?: string | null) => formatUserLong(iso, timezone),
      formatDateTime: (iso?: string | null) => formatUserDateTime(iso, timezone),
      timeLabel: (iso: string | undefined | null, spanHours: number) =>
        formatUserTimeLabel(iso, spanHours, timezone),
      mapTrafficLabels: <T extends Record<string, unknown>>(points: T[], spanHours: number, xKey = "t") =>
        mapTrafficSeriesLabels(points, spanHours, xKey, timezone),
      datePresets: () => workOrderDatePresets(timezone),
      formatRange: (start: Dayjs, end: Dayjs) => formatCustomRangeLabel(start, end, timezone),
    }),
    [timezone, locale, format],
  );
}

import type { TFunction } from "i18next";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { formatCustomRangeLabel, formatUserTimeLabel, getActiveTimezone } from "./datetime";

export type RangeMode = "preset" | "custom";

export function getHourOptions(t: TFunction) {
  return [
    { value: 1, label: t("monitor.last1h") },
    { value: 6, label: t("monitor.last6h") },
    { value: 24, label: t("monitor.last24h") },
    { value: 168, label: t("monitor.last7d") },
    { value: 720, label: t("monitor.last30d") },
  ];
}

/** @deprecated use getHourOptions(t) */
export const HOUR_OPTIONS = [
  { value: 1, label: "近 1 小时" },
  { value: 6, label: "近 6 小时" },
  { value: 24, label: "近 24 小时" },
  { value: 168, label: "近 7 天" },
  { value: 720, label: "近 30 天" },
];

export function buildRangeParams(
  mode: RangeMode,
  hours: number,
  customRange: [Dayjs, Dayjs] | null,
  tz?: string,
) {
  if (mode === "custom" && customRange) {
    const [start, end] = customRange;
    const zone = tz ?? getActiveTimezone();
    return {
      start_at: dayjs.tz(start.format("YYYY-MM-DD HH:mm:ss"), zone).toISOString(),
      end_at: dayjs.tz(end.format("YYYY-MM-DD HH:mm:ss"), zone).toISOString(),
    };
  }
  return { hours };
}

export function sampleLimitForWindow(mode: RangeMode, hours: number, customRange: [Dayjs, Dayjs] | null) {
  const spanHours =
    mode === "custom" && customRange
      ? Math.max(1, Math.ceil(customRange[1].diff(customRange[0], "hour", true)))
      : hours;
  const estimated = Math.ceil(spanHours * 120 * 1.15);
  return Math.min(Math.max(estimated, 60), 5000);
}

export function spanHoursFor(mode: RangeMode, hours: number, customRange: [Dayjs, Dayjs] | null) {
  if (mode === "custom" && customRange) {
    return Math.max(1, Math.ceil(customRange[1].diff(customRange[0], "hour", true)));
  }
  return hours;
}

export function windowLabelFor(
  mode: RangeMode,
  hours: number,
  customRange: [Dayjs, Dayjs] | null,
  t?: TFunction,
  tz?: string,
) {
  if (mode === "custom" && customRange) {
    return formatCustomRangeLabel(customRange[0], customRange[1], tz);
  }
  const options = t ? getHourOptions(t) : HOUR_OPTIONS;
  return options.find((o) => o.value === hours)?.label || (t ? t("monitor.lastNh", { hours }) : `近 ${hours}h`);
}

export function timeLabel(iso: string | undefined, spanHours: number, tz?: string) {
  return formatUserTimeLabel(iso, spanHours, tz);
}

export function chartRangeKey(
  circuitId: number,
  mode: RangeMode,
  hours: number,
  customRange: [Dayjs, Dayjs] | null,
  sampleCount: number,
  tz?: string,
) {
  const customKey =
    mode === "custom" && customRange
      ? `${customRange[0].valueOf()}-${customRange[1].valueOf()}`
      : "preset";
  return `${circuitId}-${mode}-${hours}-${customKey}-${sampleCount}-${tz || "utc"}`;
}

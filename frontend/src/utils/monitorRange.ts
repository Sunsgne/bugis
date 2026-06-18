import type { Dayjs } from "dayjs";
import dayjs from "dayjs";

export type RangeMode = "preset" | "custom";

export const HOUR_OPTIONS = [
  { value: 1, label: "近 1 小时" },
  { value: 6, label: "近 6 小时" },
  { value: 24, label: "近 24 小时" },
  { value: 168, label: "近 7 天" },
  { value: 720, label: "近 30 天" },
];

export function buildRangeParams(mode: RangeMode, hours: number, customRange: [Dayjs, Dayjs] | null) {
  if (mode === "custom" && customRange) {
    const [start, end] = customRange;
    return { start_at: start.toISOString(), end_at: end.toISOString() };
  }
  return { hours };
}

export function sampleLimitForWindow(mode: RangeMode, hours: number, customRange: [Dayjs, Dayjs] | null) {
  const spanHours =
    mode === "custom" && customRange
      ? Math.max(1, Math.ceil(customRange[1].diff(customRange[0], "hour", true)))
      : hours;
  if (spanHours <= 6) return 120;
  if (spanHours <= 24) return 288;
  if (spanHours <= 168) return 500;
  return 2000;
}

export function spanHoursFor(mode: RangeMode, hours: number, customRange: [Dayjs, Dayjs] | null) {
  if (mode === "custom" && customRange) {
    return Math.max(1, Math.ceil(customRange[1].diff(customRange[0], "hour", true)));
  }
  return hours;
}

export function windowLabelFor(mode: RangeMode, hours: number, customRange: [Dayjs, Dayjs] | null) {
  if (mode === "custom" && customRange) {
    return `${customRange[0].format("MM-DD HH:mm")} ~ ${customRange[1].format("MM-DD HH:mm")}`;
  }
  return HOUR_OPTIONS.find((o) => o.value === hours)?.label || `近 ${hours}h`;
}

export function timeLabel(iso: string | undefined, spanHours: number) {
  if (!iso) return "";
  const fmt = spanHours > 24 ? "MM-DD HH:mm" : "HH:mm";
  return dayjs(iso).format(fmt);
}

export function chartRangeKey(
  circuitId: number,
  mode: RangeMode,
  hours: number,
  customRange: [Dayjs, Dayjs] | null,
  sampleCount: number,
) {
  const customKey =
    mode === "custom" && customRange
      ? `${customRange[0].valueOf()}-${customRange[1].valueOf()}`
      : "preset";
  return `${circuitId}-${mode}-${hours}-${customKey}-${sampleCount}`;
}

/** Shared palette and typography for ECharts 6.x. */

export const chartFont =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif';

export const chartText = {
  primary: "#1e293b",
  secondary: "#64748b",
  muted: "#94a3b8",
  grid: "rgba(148, 163, 184, 0.14)",
  split: "rgba(148, 163, 184, 0.08)",
  tooltipBg: "rgba(15, 23, 42, 0.92)",
  tooltipBorder: "rgba(148, 163, 184, 0.18)",
};

export const chartGradients = {
  rx: { from: "#6366f1", to: "#38bdf8" },
  tx: { from: "#10b981", to: "#34d399" },
  bar: { from: "#6366f1", to: "#818cf8" },
  warn: { from: "#f59e0b", to: "#fbbf24" },
  danger: { from: "#ef4444", to: "#f87171" },
};

export const vendorColors: Record<string, string> = {
  h3c: "#6366f1",
  huawei: "#ef4444",
  juniper: "#10b981",
  arista: "#f59e0b",
  cisco: "#8b5cf6",
  frr: "#06b6d4",
};

export const statusColors: Record<string, string> = {
  active: "#10b981",
  draft: "#94a3b8",
  provisioning: "#6366f1",
  failed: "#ef4444",
  degraded: "#f59e0b",
  decommissioned: "#cbd5e1",
  pending: "#818cf8",
  suspended: "#fb923c",
};

export const severityColors: Record<string, string> = {
  critical: "#dc2626",
  major: "#ea580c",
  minor: "#f59e0b",
  warning: "#eab308",
  info: "#6366f1",
};

export function utilColor(p: number): string {
  return p >= 85 ? chartGradients.danger.from : p >= 60 ? chartGradients.warn.from : "#10b981";
}

export function linearGradient(
  id: string,
  from: string,
  to: string,
  direction: "vertical" | "horizontal" = "vertical",
): { type: "linear"; x: number; y: number; x2: number; y2: number; colorStops: { offset: number; color: string }[] } {
  const vertical = direction === "vertical";
  return {
    type: "linear",
    x: 0,
    y: 0,
    x2: vertical ? 0 : 1,
    y2: vertical ? 1 : 0,
    colorStops: [
      { offset: 0, color: from },
      { offset: 1, color: to },
    ],
  };
}

export function baseTooltip() {
  return {
    trigger: "axis" as const,
    backgroundColor: chartText.tooltipBg,
    borderColor: chartText.tooltipBorder,
    borderWidth: 1,
    padding: [10, 14],
    textStyle: { color: "#e2e8f0", fontSize: 12, fontFamily: chartFont },
    axisPointer: {
      type: "cross" as const,
      crossStyle: { color: chartText.muted },
      lineStyle: { color: "rgba(99, 102, 241, 0.35)", type: "dashed" as const },
    },
  };
}

export function itemTooltip() {
  return {
    trigger: "item" as const,
    backgroundColor: chartText.tooltipBg,
    borderColor: chartText.tooltipBorder,
    borderWidth: 1,
    padding: [10, 14],
    textStyle: { color: "#e2e8f0", fontSize: 12, fontFamily: chartFont },
  };
}

export function baseGrid(extra?: object) {
  return {
    left: 12,
    right: 16,
    top: 48,
    bottom: 8,
    containLabel: true,
    ...extra,
  };
}

export function baseLegend() {
  return {
    bottom: 0,
    icon: "roundRect" as const,
    itemWidth: 10,
    itemHeight: 10,
    itemGap: 16,
    textStyle: { color: chartText.secondary, fontSize: 12, fontFamily: chartFont },
  };
}

export function categoryAxis(data: string[]) {
  return {
    type: "category" as const,
    data,
    boundaryGap: false,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: chartText.secondary, fontSize: 11, fontFamily: chartFont },
  };
}

export function valueAxis(formatter?: (v: number) => string) {
  return {
    type: "value" as const,
    splitLine: { lineStyle: { color: chartText.split, type: "dashed" as const } },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: chartText.muted,
      fontSize: 11,
      fontFamily: chartFont,
      formatter: formatter ? (v: number) => formatter(v) : undefined,
    },
  };
}

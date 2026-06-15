import type { EChartsOption } from "echarts";
import type { CallbackDataParams } from "echarts/types/dist/shared";
import {
  baseGrid,
  baseLegend,
  baseTooltip,
  categoryAxis,
  chartFont,
  chartGradients,
  chartText,
  itemTooltip,
  linearGradient,
  severityColors,
  statusColors,
  utilColor,
  valueAxis,
  vendorColors,
} from "./theme";

type Point = { name: string; value: number };
type SeriesPoint = Record<string, string | number>;

function fmtMbps(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}T`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}G`;
  return `${Math.round(v)}`;
}

/** Dual Rx/Tx area chart for network traffic. */
export function trafficAreaOption(
  data: SeriesPoint[],
  xKey: string,
  rxKey = "rx",
  txKey = "tx",
): EChartsOption {
  const categories = data.map((d) => String(d[xKey]));
  return {
    animationDuration: 800,
    animationEasing: "cubicOut",
    grid: baseGrid({ bottom: 36 }),
    tooltip: {
      ...baseTooltip(),
      formatter: (params) => {
        const list = (Array.isArray(params) ? params : [params]) as CallbackDataParams[];
        const rows = list
          .map((p) => {
            const v = Number(p.value);
            return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: <b>${fmtMbps(v)} Mbps</b>`;
          })
          .join("<br/>");
        const axis = list[0]?.name ?? "";
        return `<div style="font-weight:600;margin-bottom:6px">${axis}</div>${rows}`;
      },
    },
    legend: { ...baseLegend(), data: ["Rx", "Tx"] },
    xAxis: categoryAxis(categories),
    yAxis: valueAxis(fmtMbps),
    series: [
      {
        name: "Rx",
        type: "line",
        smooth: 0.35,
        showSymbol: false,
        lineStyle: { width: 2.5, color: chartGradients.rx.from },
        areaStyle: {
          color: linearGradient("rx", chartGradients.rx.from, chartGradients.rx.to),
          opacity: 0.22,
        },
        emphasis: { focus: "series" as const },
        data: data.map((d) => Number(d[rxKey] ?? 0)),
      },
      {
        name: "Tx",
        type: "line",
        smooth: 0.35,
        showSymbol: false,
        lineStyle: { width: 2.5, color: chartGradients.tx.from },
        areaStyle: {
          color: linearGradient("tx", chartGradients.tx.from, chartGradients.tx.to),
          opacity: 0.18,
        },
        emphasis: { focus: "series" as const },
        data: data.map((d) => Number(d[txKey] ?? 0)),
      },
    ],
  };
}

/** Donut chart with center total — alarm severity, etc. */
export function donutOption(
  data: Point[],
  colorMap: Record<string, string>,
  centerLabel = "总计",
): EChartsOption {
  const total = data.reduce((s, d) => s + d.value, 0);
  const colored = data.map((d) => ({
    ...d,
    itemStyle: {
      color: colorMap[d.name] ?? "#94a3b8",
      borderRadius: 6,
      borderColor: "#fff",
      borderWidth: 2,
      shadowBlur: 8,
      shadowColor: "rgba(99, 102, 241, 0.15)",
    },
  }));

  return {
    animationDuration: 900,
    animationEasing: "elasticOut",
    tooltip: {
      ...itemTooltip(),
      formatter: (params) => {
        const p = params as CallbackDataParams;
        const pct = total ? ((Number(p.value) / total) * 100).toFixed(1) : "0";
        return `<b>${p.name}</b><br/>${p.value} 条 · ${pct}%`;
      },
    },
    legend: {
      ...baseLegend(),
      orient: "horizontal" as const,
      formatter: (name: string) => {
        const item = data.find((d) => d.name === name);
        return item ? `${name}  ${item.value}` : name;
      },
    },
    title: total
      ? {
          text: String(total),
          subtext: centerLabel,
          left: "center",
          top: "38%",
          textAlign: "center",
          textStyle: { fontSize: 28, fontWeight: 700, color: chartText.primary, fontFamily: chartFont },
          subtextStyle: { fontSize: 12, color: chartText.muted, fontFamily: chartFont },
        }
      : undefined,
    series: [
      {
        type: "pie",
        radius: ["52%", "74%"],
        center: ["50%", "46%"],
        padAngle: 2,
        avoidLabelOverlap: true,
        label: { show: false },
        emphasis: {
          scale: true,
          scaleSize: 6,
          itemStyle: { shadowBlur: 16, shadowColor: "rgba(0,0,0,0.12)" },
        },
        data: colored,
      },
    ],
  };
}

/** Nightingale / rose pie for categorical distribution. */
export function rosePieOption(data: Point[], colorMap: Record<string, string>): EChartsOption {
  return {
    animationDuration: 900,
    animationEasing: "cubicOut",
    tooltip: {
      ...itemTooltip(),
      formatter: (params) => {
        const p = params as CallbackDataParams;
        return `<b>${p.name}</b><br/>${p.value} 台`;
      },
    },
    legend: { ...baseLegend(), type: "scroll" as const },
    series: [
      {
        type: "pie",
        radius: ["18%", "72%"],
        center: ["50%", "44%"],
        roseType: "area",
        itemStyle: {
          borderRadius: 8,
          borderColor: "#fff",
          borderWidth: 2,
        },
        label: {
          formatter: "{b}",
          color: chartText.secondary,
          fontSize: 11,
          fontFamily: chartFont,
        },
        labelLine: { length: 8, length2: 12, lineStyle: { color: chartText.muted } },
        emphasis: {
          itemStyle: { shadowBlur: 14, shadowColor: "rgba(99, 102, 241, 0.25)" },
        },
        data: data.map((d) => ({
          ...d,
          itemStyle: { color: colorMap[d.name] ?? "#6366f1" },
        })),
      },
    ],
  };
}

/** Gradient rounded bar chart for status / utilization. */
export function gradientBarOption(
  data: Point[],
  colorMap: Record<string, string>,
  ySuffix = "",
): EChartsOption {
  return {
    animationDuration: 700,
    animationEasing: "cubicOut",
    grid: baseGrid({ bottom: 4 }),
    tooltip: {
      ...baseTooltip(),
      trigger: "axis",
      axisPointer: { type: "shadow" as const },
      formatter: (params) => {
        const p = (Array.isArray(params) ? params[0] : params) as CallbackDataParams;
        return `<b>${p.name}</b><br/>${p.value}${ySuffix}`;
      },
    },
    xAxis: {
      type: "category",
      data: data.map((d) => d.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: chartText.secondary,
        fontSize: 11,
        fontFamily: chartFont,
        interval: 0,
        rotate: data.length > 4 ? 18 : 0,
      },
    },
    yAxis: {
      ...valueAxis(),
      minInterval: 1,
    },
    series: [
      {
        type: "bar",
        barWidth: "46%",
        data: data.map((d) => ({
          value: d.value,
          itemStyle: {
            color: linearGradient(
              d.name,
              colorMap[d.name] ?? chartGradients.bar.from,
              colorMap[d.name] ? `${colorMap[d.name]}99` : chartGradients.bar.to,
            ),
            borderRadius: [8, 8, 0, 0],
            shadowBlur: 6,
            shadowColor: "rgba(99, 102, 241, 0.12)",
          },
        })),
        emphasis: {
          itemStyle: { shadowBlur: 14, shadowColor: "rgba(99, 102, 241, 0.28)" },
        },
      },
    ],
  };
}

/** Horizontal utilization bars for link capacity. */
export function linkUtilBarOption(data: { name: string; util: number }[]): EChartsOption {
  const names = data.map((d) => d.name);
  return {
    animationDuration: 700,
    grid: baseGrid({ left: 8, right: 24, top: 8, bottom: 8 }),
    tooltip: {
      ...baseTooltip(),
      trigger: "axis",
      axisPointer: { type: "shadow" as const },
      formatter: (params) => {
        const p = (Array.isArray(params) ? params[0] : params) as CallbackDataParams;
        return `<b>${p.name}</b><br/>峰值利用率 <b>${p.value}%</b>`;
      },
    },
    xAxis: {
      type: "value",
      max: 100,
      splitLine: { lineStyle: { color: chartText.split, type: "dashed" } },
      axisLabel: { color: chartText.muted, formatter: "{value}%" },
    },
    yAxis: {
      type: "category",
      data: names,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: chartText.secondary, fontSize: 11, width: 120, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        barWidth: 14,
        data: data.map((d) => ({
          value: d.util,
          itemStyle: {
            color: linearGradient(d.name, utilColor(d.util), `${utilColor(d.util)}88`),
            borderRadius: [0, 8, 8, 0],
          },
        })),
        showBackground: true,
        backgroundStyle: { color: "rgba(148, 163, 184, 0.12)", borderRadius: [0, 8, 8, 0] },
      },
    ],
  };
}

/** Dual-axis line chart for latency + packet loss. */
export function latencyLossOption(data: SeriesPoint[]): EChartsOption {
  const categories = data.map((_, i) => String(i + 1));
  return {
    animationDuration: 800,
    grid: baseGrid({ bottom: 36 }),
    tooltip: {
      ...baseTooltip(),
      formatter: (params) => {
        const list = (Array.isArray(params) ? params : [params]) as CallbackDataParams[];
        const rows = list
          .map((p) => {
            const unit = p.seriesName?.includes("丢包") ? "%" : " ms";
            return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: <b>${p.value}${unit}</b>`;
          })
          .join("<br/>");
        return `<div style="font-weight:600;margin-bottom:6px">采样 #${list[0]?.name ?? ""}</div>${rows}`;
      },
    },
    legend: { ...baseLegend(), data: ["时延 (ms)", "丢包 (%)"] },
    xAxis: categoryAxis(categories),
    yAxis: [
      {
        ...valueAxis(),
        name: "时延",
        nameTextStyle: { color: chartGradients.warn.from, fontSize: 11 },
        axisLabel: { color: chartText.muted, formatter: "{value}" },
      },
      {
        ...valueAxis(),
        name: "丢包",
        nameTextStyle: { color: severityColors.critical, fontSize: 11 },
        splitLine: { show: false },
        axisLabel: { color: chartText.muted, formatter: "{value}%" },
      },
    ],
    series: [
      {
        name: "时延 (ms)",
        type: "line",
        smooth: 0.35,
        showSymbol: false,
        yAxisIndex: 0,
        lineStyle: { width: 2.5, color: chartGradients.warn.from },
        areaStyle: {
          color: linearGradient("lat", chartGradients.warn.from, chartGradients.warn.to),
          opacity: 0.15,
        },
        data: data.map((d) => Number(d.latency ?? 0)),
      },
      {
        name: "丢包 (%)",
        type: "line",
        smooth: 0.35,
        showSymbol: false,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: severityColors.critical, type: "dashed" },
        data: data.map((d) => Number(d.loss ?? 0)),
      },
    ],
  };
}

export { severityColors, statusColors, vendorColors, utilColor };

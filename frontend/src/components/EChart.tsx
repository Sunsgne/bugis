import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, BarChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
]);

type Props = {
  option: EChartsOption;
  height?: number;
  className?: string;
};

export default function EChart({ option, height = 280, className }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!host.current) return;
    chart.current = echarts.init(host.current, undefined, { renderer: "canvas" });
    const onResize = () => chart.current?.resize();
    const ro = new ResizeObserver(onResize);
    ro.observe(host.current);
    window.addEventListener("resize", onResize);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", onResize);
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    if (!chart.current) return;
    chart.current.setOption(option, { notMerge: true });
  }, [option]);

  return (
    <div
      ref={host}
      className={className}
      style={{ width: "100%", height, minHeight: height }}
    />
  );
}

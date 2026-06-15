import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { GraphChart } from "echarts/charts";
import { TooltipComponent, LegendComponent, GraphicComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";

echarts.use([GraphChart, TooltipComponent, LegendComponent, GraphicComponent, CanvasRenderer]);

type Props = {
  option: EChartsOption | null;
  height?: number;
  className?: string;
};

export default function TopologyGraph({ option, height = 560, className }: Props) {
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
    if (!chart.current || !option) return;
    chart.current.setOption(option, { notMerge: true });
  }, [option]);

  return (
    <div
      ref={host}
      className={["topology-graph", className].filter(Boolean).join(" ")}
      style={{ width: "100%", height, minHeight: height }}
    />
  );
}

import type { LinkUsage } from "@/api/types";
import dayjs from "dayjs";

export function fmtLinkBw(mbps?: number) {
  if (!mbps) return "—";
  return mbps >= 1000 ? `${Math.round(mbps / 1000)} Gbps` : `${mbps} Mbps`;
}

export function formatPeakAt(iso?: string | null) {
  if (!iso) return "—";
  return dayjs(iso).format("YYYY-MM-DD HH:mm:ss");
}

/** Backbone link utilization color: green &lt;50%, amber 50–84%, red ≥85%. */
export function backboneUtilColor(pct: number): string {
  if (pct < 50) return "#22c55e";
  if (pct < 85) return "#f59e0b";
  return "#ef4444";
}

type Tc = (zh: string) => string;

export function linkUtilizationLines(r: LinkUsage, pct: number, tc: Tc = (s) => s): string[] {
  const peakRx = r.peak_rx_mbps ?? 0;
  const peakTx = r.peak_tx_mbps ?? 0;
  const peakTotal = r.peak_traffic_mbps ?? peakRx + peakTx;
  const lines = [
    `${tc("峰值利用率")} ${Math.round(pct)}%`,
    `${tc("峰值带宽")} Rx ${fmtLinkBw(peakRx)} / Tx ${fmtLinkBw(peakTx)} · ${tc("合计")} ${fmtLinkBw(peakTotal)}`,
    `${tc("合同带宽")} ${fmtLinkBw(r.capacity_mbps)}`,
    `${tc("采样时间")} ${formatPeakAt(r.peak_at)}`,
  ];
  if (r.traffic_mbps != null && r.traffic_mbps > 0) {
    lines.push(`${tc("当前流量")} ${fmtLinkBw(r.traffic_mbps)}`);
  }
  if (r.effective_alarm_utilization_pct != null) {
    lines.push(`${tc("告警阈值")} ${r.effective_alarm_utilization_pct}%`);
  }
  return lines;
}

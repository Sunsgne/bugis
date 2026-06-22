import { Tag } from "antd";
import type { LinkUsage } from "@/api/types";
import {
  backboneUtilColor,
  fmtLinkBw,
  formatPeakAt,
} from "@/utils/linkUtilization";
import { formatInterfaceShort } from "@/utils/networkDisplay";

const LINK_TYPE_LABEL: Record<string, string> = {
  dci: "跨站点 DCI",
  intra_dc: "站内互联",
  access: "接入",
  uplink: "上联",
};

function siteRouteLabel(r: LinkUsage) {
  const a = r.site_a_code || r.site_a || "—";
  const z = r.site_z_code || r.site_z || "—";
  return `${a} → ${z}`;
}

function shortText(text: string, max = 42): string {
  if (text.length <= max) return text;
  const head = Math.ceil((max - 1) * 0.55);
  const tail = max - head - 1;
  return `${text.slice(0, head)}…${text.slice(-tail)}`;
}

function EndpointCard({
  side,
  device,
  iface,
  description,
  tc,
}: {
  side: "A" | "Z";
  device: string;
  iface?: string;
  description?: string | null;
  tc: (zh: string) => string;
}) {
  const desc = description?.trim();
  const ifaceShort = iface ? formatInterfaceShort(iface) : null;

  return (
    <div className={`link-util-tooltip-endpoint link-util-tooltip-endpoint-${side.toLowerCase()}`}>
      <div className="link-util-tooltip-endpoint-head">
        <span className="link-util-tooltip-endpoint-badge">{tc(`${side} 端`)}</span>
      </div>
      <div className="link-util-tooltip-device" title={device}>
        {shortText(device, 38)}
      </div>
      {ifaceShort ? (
        <div className="link-util-tooltip-iface" title={iface}>
          {ifaceShort}
        </div>
      ) : null}
      {desc ? (
        <div className="link-util-tooltip-desc" title={desc}>
          {shortText(desc, 52)}
        </div>
      ) : null}
    </div>
  );
}

type Props = {
  link: LinkUsage;
  pct: number;
  tc: (zh: string) => string;
};

export default function LinkUtilizationTooltipContent({ link, pct, tc }: Props) {
  const utilColor = backboneUtilColor(pct);
  const peakRx = link.peak_rx_mbps ?? 0;
  const peakTx = link.peak_tx_mbps ?? 0;
  const peakTotal = link.peak_traffic_mbps ?? peakRx + peakTx;
  const utilRounded = Math.round(pct);

  return (
    <div className="link-util-tooltip">
      <div className="link-util-tooltip-header">
        <div className="link-util-tooltip-title-row">
          <span className="link-util-tooltip-title">{link.name}</span>
          {link.supplier ? (
            <span className="link-util-tooltip-supplier">{link.supplier}</span>
          ) : null}
        </div>
        <div className="link-util-tooltip-tags">
          <Tag bordered={false} color={link.type === "dci" ? "blue" : "green"} className="link-util-tooltip-type">
            {tc(LINK_TYPE_LABEL[link.type] || link.type)}
          </Tag>
          <span className="link-util-tooltip-route">{siteRouteLabel(link)}</span>
        </div>
      </div>

      <div className="link-util-tooltip-util">
        <div className="link-util-tooltip-util-head">
          <span>{tc("峰值利用率")}</span>
          <span className="link-util-tooltip-util-pct" style={{ color: utilColor }}>
            {utilRounded}%
          </span>
        </div>
        <div className="link-util-tooltip-util-track">
          <div
            className="link-util-tooltip-util-fill"
            style={{ width: `${Math.min(100, Math.max(0, utilRounded))}%`, background: utilColor }}
          />
        </div>
      </div>

      <div className="link-util-tooltip-endpoints">
        <EndpointCard
          side="A"
          device={link.device_a}
          iface={link.interface_a}
          description={link.interface_a_description}
          tc={tc}
        />
        <div className="link-util-tooltip-endpoint-divider" aria-hidden>
          <span />
        </div>
        <EndpointCard
          side="Z"
          device={link.device_z}
          iface={link.interface_z}
          description={link.interface_z_description}
          tc={tc}
        />
      </div>

      <div className="link-util-tooltip-metrics">
        <div className="link-util-tooltip-metric">
          <span className="link-util-tooltip-metric-label">{tc("峰值带宽")}</span>
          <span className="link-util-tooltip-metric-value">
            Rx {fmtLinkBw(peakRx)} · Tx {fmtLinkBw(peakTx)}
          </span>
        </div>
        <div className="link-util-tooltip-metric">
          <span className="link-util-tooltip-metric-label">{tc("合计")}</span>
          <span className="link-util-tooltip-metric-value">{fmtLinkBw(peakTotal)}</span>
        </div>
        <div className="link-util-tooltip-metric">
          <span className="link-util-tooltip-metric-label">{tc("合同带宽")}</span>
          <span className="link-util-tooltip-metric-value link-util-tooltip-metric-highlight">
            {fmtLinkBw(link.capacity_mbps)}
          </span>
        </div>
        <div className="link-util-tooltip-metric">
          <span className="link-util-tooltip-metric-label">{tc("采样时间")}</span>
          <span className="link-util-tooltip-metric-value link-util-tooltip-metric-mono">
            {formatPeakAt(link.peak_at)}
          </span>
        </div>
        {link.traffic_mbps != null && link.traffic_mbps > 0 ? (
          <div className="link-util-tooltip-metric">
            <span className="link-util-tooltip-metric-label">{tc("当前流量")}</span>
            <span className="link-util-tooltip-metric-value">{fmtLinkBw(link.traffic_mbps)}</span>
          </div>
        ) : null}
        {link.effective_alarm_utilization_pct != null ? (
          <div className="link-util-tooltip-metric">
            <span className="link-util-tooltip-metric-label">{tc("告警阈值")}</span>
            <span className="link-util-tooltip-metric-value">{link.effective_alarm_utilization_pct}%</span>
          </div>
        ) : null}
        {link.samples != null ? (
          <div className="link-util-tooltip-metric">
            <span className="link-util-tooltip-metric-label">{tc("SNMP 样本")}</span>
            <span className="link-util-tooltip-metric-value">
              {link.samples > 0 ? link.samples : tc("暂无 · 请确认设备在线并对两端执行 SNMP 发现")}
            </span>
          </div>
        ) : null}
        {link.backbone_link && link.igp_cost_a != null ? (
          <div className="link-util-tooltip-metric">
            <span className="link-util-tooltip-metric-label">{tc("IGP Cost")}</span>
            <span className="link-util-tooltip-metric-value">
              OSPF {link.igp_process_a ?? "—"} · {link.igp_cost_a}
            </span>
          </div>
        ) : link.igp_a?.backbone || link.igp_z?.backbone ? (
          <div className="link-util-tooltip-metric">
            <span className="link-util-tooltip-metric-label">{tc("IGP Cost")}</span>
            <span className="link-util-tooltip-metric-value">
              {[
                link.igp_a?.backbone ? `A:${link.igp_a.igp_cost}` : null,
                link.igp_z?.backbone ? `Z:${link.igp_z.igp_cost}` : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

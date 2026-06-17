import { Button, Empty, Popconfirm, Progress, Tag, Tooltip } from "antd";
import { DeleteOutlined, SwapRightOutlined } from "@ant-design/icons";
import type { LinkUsage } from "../api/types";
import InterfaceNameCell from "./InterfaceNameCell";
import { utilColor } from "../charts/options";

const LINK_TYPE_LABEL: Record<string, string> = {
  dci: "跨站点 DCI",
  intra_dc: "站内互联",
  access: "接入",
  uplink: "上联",
};

function fmtBw(mbps: number) {
  return mbps >= 1000 ? `${Math.round(mbps / 1000)} Gbps` : `${mbps} Mbps`;
}

function shortHost(name: string) {
  const dot = name.indexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}

interface Props {
  links: LinkUsage[];
  onDelete: (linkId: number) => void;
}

export default function BackboneLinkCards({ links, onDelete }: Props) {
  if (links.length === 0) {
    return <Empty description="暂无链路 · 点击「配置骨干链路」智能推荐或手动选配" />;
  }

  return (
    <div className="backbone-link-grid">
      {links.map((link) => {
        const util = link.utilization_pct ?? 0;
        const utilStroke = utilColor(util);
        return (
          <article key={link.link_id} className="backbone-link-card">
            <header className="backbone-link-card-head">
              <div className="backbone-link-card-title">
                <span className="backbone-link-card-name">{link.name}</span>
                <Tag color="processing" bordered={false}>
                  {LINK_TYPE_LABEL[link.type] || link.type}
                </Tag>
              </div>
              <Popconfirm title="删除此骨干链路？" onConfirm={() => onDelete(link.link_id)}>
                <Button type="text" size="small" danger icon={<DeleteOutlined />} aria-label="删除" />
              </Popconfirm>
            </header>

            <div className="backbone-link-endpoints">
              <div className="backbone-link-endpoint">
                <span className="backbone-link-endpoint-label">A</span>
                <div className="backbone-link-endpoint-body">
                  <Tooltip title={link.device_a}>
                    <span className="backbone-link-host">{shortHost(link.device_a)}</span>
                  </Tooltip>
                  {link.interface_a ? (
                    <InterfaceNameCell name={link.interface_a} />
                  ) : (
                    <span className="backbone-link-port-muted">—</span>
                  )}
                </div>
              </div>
              <SwapRightOutlined className="backbone-link-arrow" />
              <div className="backbone-link-endpoint">
                <span className="backbone-link-endpoint-label">Z</span>
                <div className="backbone-link-endpoint-body">
                  <Tooltip title={link.device_z}>
                    <span className="backbone-link-host">{shortHost(link.device_z)}</span>
                  </Tooltip>
                  {link.interface_z ? (
                    <InterfaceNameCell name={link.interface_z} />
                  ) : (
                    <span className="backbone-link-port-muted">—</span>
                  )}
                </div>
              </div>
            </div>

            <div className="backbone-link-metrics">
              <div className="backbone-link-metric">
                <span className="backbone-link-metric-label">合同带宽</span>
                <span className="backbone-link-metric-value">{fmtBw(link.capacity_mbps)}</span>
              </div>
              <div className="backbone-link-metric">
                <span className="backbone-link-metric-label">实时流量</span>
                <span className="backbone-link-metric-value">
                  {link.traffic_mbps != null ? fmtBw(link.traffic_mbps) : "—"}
                </span>
              </div>
              <div className="backbone-link-metric backbone-link-metric-util">
                <span className="backbone-link-metric-label">峰值利用率</span>
                <div className="backbone-link-util-row">
                  <span className="backbone-link-util-pct" style={{ color: utilStroke }}>
                    {util}%
                  </span>
                  <Progress
                    percent={util}
                    showInfo={false}
                    strokeColor={utilStroke}
                    trailColor="rgba(148, 163, 184, 0.18)"
                    size="small"
                    className="backbone-link-util-bar"
                  />
                </div>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}

import { Divider, Space, Tag, Typography } from "antd";
import type { LinkUsage } from "@/api/types";
import { linkUtilizationLines } from "@/utils/linkUtilization";
import InterfaceNameCell from "./InterfaceNameCell";

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

function EndpointBlock({
  label,
  device,
  iface,
  description,
}: {
  label: string;
  device: string;
  iface?: string;
  description?: string | null;
}) {
  const desc = description?.trim();
  return (
    <div>
      <Typography.Text type="secondary" style={{ fontSize: 11 }}>
        {label}
      </Typography.Text>
      <div style={{ fontSize: 12 }}>{device}</div>
      {iface ? <InterfaceNameCell name={iface} copyable={false} /> : null}
      {desc ? (
        <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 2 }}>
          {desc}
        </Typography.Text>
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
  return (
    <div style={{ lineHeight: 1.6, maxWidth: 400 }}>
      <Space wrap size={4}>
        <strong>{link.name}</strong>
        {link.supplier ? <span>{link.supplier}</span> : null}
        <Tag color={link.type === "dci" ? "blue" : "green"} style={{ margin: 0 }}>
          {tc(LINK_TYPE_LABEL[link.type] || link.type)}
        </Tag>
      </Space>
      <div style={{ marginTop: 4, fontSize: 12 }}>{siteRouteLabel(link)}</div>
      <Divider style={{ margin: "8px 0", borderColor: "rgba(255,255,255,0.12)" }} />
      <EndpointBlock
        label={tc("A 端")}
        device={link.device_a}
        iface={link.interface_a}
        description={link.interface_a_description}
      />
      <div style={{ marginTop: 6 }}>
        <EndpointBlock
          label={tc("Z 端")}
          device={link.device_z}
          iface={link.interface_z}
          description={link.interface_z_description}
        />
      </div>
      <Divider style={{ margin: "8px 0", borderColor: "rgba(255,255,255,0.12)" }} />
      {linkUtilizationLines(link, pct, tc).map((line) => (
        <div key={line}>{line}</div>
      ))}
    </div>
  );
}

import { Tag, Typography } from "antd";

export type MultipointEndpoint = {
  label: string;
  device_name: string;
  interface?: string;
  vlan?: string;
  vtep_ip?: string;
  access_mode?: string;
};

type Props = {
  vni?: number | null;
  vsi_name?: string | null;
  rd?: string | null;
  rt?: string | null;
  endpoints: MultipointEndpoint[];
};

export default function MultipointEvpnDiagram({ vni, vsi_name, rd, rt, endpoints }: Props) {
  if (!endpoints.length) return null;

  return (
    <div className="multipoint-evpn-diagram">
      <div className="multipoint-evpn-hub">
        <div className="multipoint-evpn-hub-badge">EVPN</div>
        <Typography.Text strong style={{ fontSize: 13 }}>
          VNI {vni ?? "—"}
        </Typography.Text>
        {vsi_name ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {vsi_name}
          </Typography.Text>
        ) : null}
        {(rd || rt) && (
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>
            {rd ? `RD ${rd}` : ""}
            {rd && rt ? " · " : ""}
            {rt ? `RT ${rt}` : ""}
          </Typography.Text>
        )}
        <Typography.Text type="secondary" style={{ fontSize: 11, marginTop: 4 }}>
          多点二层互通
        </Typography.Text>
      </div>

      <div className="multipoint-evpn-spokes">
        {endpoints.map((ep) => (
          <div key={ep.label} className="multipoint-evpn-spoke">
            <div className="multipoint-evpn-spoke-line" aria-hidden />
            <div className="multipoint-evpn-spoke-card">
              <Tag color="blue" style={{ margin: 0 }}>
                端点 {ep.label}
              </Tag>
              <Typography.Text strong style={{ fontSize: 12, display: "block", marginTop: 6 }}>
                {ep.device_name}
              </Typography.Text>
              {ep.interface ? (
                <Typography.Text type="secondary" style={{ fontSize: 11, display: "block" }}>
                  {ep.interface}
                </Typography.Text>
              ) : null}
              {ep.vlan ? (
                <Typography.Text type="secondary" style={{ fontSize: 11, display: "block" }}>
                  {ep.vlan}
                </Typography.Text>
              ) : null}
              {ep.vtep_ip ? (
                <Typography.Text type="secondary" style={{ fontSize: 11, display: "block" }}>
                  VTEP {ep.vtep_ip}
                </Typography.Text>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

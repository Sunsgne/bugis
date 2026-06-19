import { Button, Card, Col, Descriptions, Row, Space, Tag, Typography } from "antd";
import type { ReactNode } from "react";
import { EditOutlined } from "@ant-design/icons";
import type { Circuit, CircuitEndpoint } from "../api/types";
import InterfaceNameCell from "./InterfaceNameCell";
import { useTc } from "@/i18n/useTc";
import { useTranslation } from "react-i18next";
import { accessModeLabel } from "../i18n/helpers";

function endpointVlanLabel(ep: CircuitEndpoint, tc: (s: string) => string): string {
  const mode = ep.access_mode || "dot1q";
  if (mode === "access") return tc("无 (Access 模式)");
  if (mode === "qinq") {
    if (ep.vlan_id == null && ep.inner_vlan_id == null) return tc("自动分配");
    const s = ep.vlan_id != null ? `S:${ep.vlan_id}` : tc("S:自动");
    const c = ep.inner_vlan_id != null ? `C:${ep.inner_vlan_id}` : ep.inner_vlan_id === undefined ? "" : tc("C:自动");
    return c ? `${s} / ${c}` : s;
  }
  return ep.vlan_id != null ? `S-VID ${ep.vlan_id}` : tc("自动分配");
}

function endpointTagColor(label: string): string {
  if (label === "A") return "blue";
  if (label === "Z") return "purple";
  return "default";
}

function EndpointFields({ children }: { children: ReactNode }) {
  return <div className="endpoint-fields">{children}</div>;
}

function EndpointField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="endpoint-field">
      <span className="endpoint-field-label">{label}</span>
      <span className="endpoint-field-value">{children}</span>
    </div>
  );
}

type Props = {
  detail: Circuit;
  deviceName: (id: number) => string | number;
  siteName: (id?: number) => string | number | undefined;
  canEditEndpoints: boolean;
  onEditEndpoints: () => void;
};

export default function CircuitExpandDetail({
  detail,
  deviceName,
  siteName,
  canEditEndpoints,
  onEditEndpoints,
}: Props) {
  const { tc } = useTc();
  const { t } = useTranslation();
  const endpoints = [...(detail.endpoints || [])].sort((a, b) => {
    if (a.label === "A") return -1;
    if (b.label === "A") return 1;
    return a.label.localeCompare(b.label);
  });

  return (
    <div className="circuit-expand-detail" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 10, fontSize: 12 }}>
          {tc("SLA 告警阈值")}
          {detail.alarm_thresholds_customized ? (
            <Typography.Text type="warning" style={{ marginLeft: 8 }}>{tc('已自定义')}</Typography.Text>
          ) : (
            <Typography.Text style={{ marginLeft: 8 }}>{tc('继承平台默认')}</Typography.Text>
          )}
          <Typography.Text style={{ marginLeft: 8 }}>
            · {tc("延迟探测")} {detail.latency_probe_enabled !== false ? tc("开启") : tc("关闭")}
          </Typography.Text>
        </Typography.Text>
        <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 4 }} bordered>
          {detail.latency_probe_enabled !== false && (
            <>
              <Descriptions.Item label={tc('时延')}>
                {detail.effective_alarm_latency_ms != null ? `${detail.effective_alarm_latency_ms} ms` : "—"}
              </Descriptions.Item>
              <Descriptions.Item label={tc('丢包')}>
                {detail.effective_alarm_packet_loss_pct != null
                  ? `${detail.effective_alarm_packet_loss_pct}%`
                  : "—"}
              </Descriptions.Item>
            </>
          )}
          <Descriptions.Item label={tc('峰值利用率')}>
            {detail.effective_alarm_utilization_pct != null
              ? `${detail.effective_alarm_utilization_pct}%`
              : "—"}
          </Descriptions.Item>
          <Descriptions.Item label={tc('健康分下限')}>
            {detail.effective_alarm_health_score_min != null
              ? `${detail.effective_alarm_health_score_min}`
              : "—"}
          </Descriptions.Item>
        </Descriptions>
      </div>

      <div>
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 10, fontSize: 12 }}>{tc('EVPN 业务标识（两端共享）')}</Typography.Text>
        <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }} bordered>
          <Descriptions.Item label="VNI">{detail.vni ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="VSI">{detail.vsi_name || "—"}</Descriptions.Item>
          <Descriptions.Item label="MTU">{detail.mtu ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="VRF">{detail.vrf_name || "—"}</Descriptions.Item>
          <Descriptions.Item label="RD">{detail.route_distinguisher || "—"}</Descriptions.Item>
          <Descriptions.Item label="RT">{detail.route_target || "—"}</Descriptions.Item>
        </Descriptions>
      </div>

      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>{tc('接入端点（A / Z 独立配置，VLAN 与封装可不同）')}</Typography.Text>
          {canEditEndpoints && (
            <Button size="small" type="link" icon={<EditOutlined />} onClick={onEditEndpoints}>
              {detail.adopted ? tc("添加端点（不下发）") : tc("修改端点并重新下发")}
            </Button>
          )}
        </div>
        <Row gutter={[16, 16]}>
          {endpoints.map((ep) => (
            <Col key={ep.id} xs={24} lg={endpoints.length > 1 ? 12 : 24}>
              <Card
                size="small"
                className="endpoint-card"
                title={
                  <Tag color={endpointTagColor(ep.label)} style={{ margin: 0 }}>
                    {tc("端点")} {ep.label}
                  </Tag>
                }
              >
                <EndpointFields>
                  <EndpointField label={tc('接入设备')}>{deviceName(ep.device_id)}</EndpointField>
                  <EndpointField label={tc('物理端口')}>
                    {ep.interface_name ? <InterfaceNameCell name={ep.interface_name} /> : "—"}
                  </EndpointField>
                  <EndpointField label={tc('封装模式')}>
                    {accessModeLabel(t, ep.access_mode || "dot1q")}
                  </EndpointField>
                  <EndpointField label="VLAN">{endpointVlanLabel(ep, tc)}</EndpointField>
                  {ep.gateway_ip ? <EndpointField label={tc('网关')}>{ep.gateway_ip}</EndpointField> : null}
                  {ep.ip_address ? <EndpointField label={tc('接口 IP')}>{ep.ip_address}</EndpointField> : null}
                </EndpointFields>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {detail.service_type === "remote_ipt" && (
        <div>
          <Typography.Text type="secondary" style={{ display: "block", marginBottom: 10, fontSize: 12 }}>{tc('Remote IPT 出口')}</Typography.Text>
          <Descriptions size="small" column={{ xs: 1, sm: 2, lg: 3 }} bordered>
            <Descriptions.Item label={tc('出口国家')}>{detail.egress_country || "—"}</Descriptions.Item>
            <Descriptions.Item label={tc('出口站点')}>{siteName(detail.egress_site_id)}</Descriptions.Item>
            <Descriptions.Item label={tc('公网 IP')}>{detail.ipt_public_ip || "—"}</Descriptions.Item>
            <Descriptions.Item label="NAT">{detail.ipt_nat_enabled ? tc("启用") : tc("关闭")}</Descriptions.Item>
          </Descriptions>
        </div>
      )}

      {(detail.path_mode === "explicit_sr" || (detail.path_hops && detail.path_hops.length > 0)) && (
        <div>
          <Typography.Text type="secondary" style={{ display: "block", marginBottom: 10, fontSize: 12 }}>{tc('Underlay 路径')}</Typography.Text>
          <Space wrap>
            <Tag color="purple">{detail.path_mode || "auto"}</Tag>
            {(detail.path_hops || []).map((h) => (
              <Tag key={h.sequence}>
                #{h.sequence + 1} {h.device_name || h.device_id}
              </Tag>
            ))}
            {detail.segment_list && detail.segment_list.length > 0 && (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                SID: {detail.segment_list.join(" → ")}
              </Typography.Text>
            )}
          </Space>
        </div>
      )}
    </div>
  );
}

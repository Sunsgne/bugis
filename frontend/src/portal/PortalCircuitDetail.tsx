import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Breadcrumb, Card, Descriptions, Spin, Tag, Typography } from "antd";
import { api } from "../api/client";
import PortalCircuitMonitorPanel from "../components/PortalCircuitMonitorPanel";

const STATUS: Record<string, { label: string; color: string }> = {
  active: { label: "运行中", color: "green" },
  degraded: { label: "降级", color: "orange" },
  provisioning: { label: "开通中", color: "processing" },
};

interface Detail {
  id: number;
  code: string;
  name: string;
  description?: string;
  status: string;
  bandwidth_mbps: number;
  service_type: string;
  vni?: number;
  vsi_name?: string;
  sla_target?: string;
  endpoints: {
    label: string;
    interface_name: string;
    access_mode?: string;
    vlan_id?: number;
    interface_description?: string;
  }[];
}

export default function PortalCircuitDetail() {
  const { id } = useParams();
  const circuitId = Number(id);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!circuitId) return;
    setLoading(true);
    api
      .get<Detail>(`/portal/circuits/${circuitId}`)
      .then((r) => setDetail(r.data))
      .finally(() => setLoading(false));
  }, [circuitId]);

  if (loading || !detail) {
    return <Spin style={{ display: "block", margin: "80px auto" }} />;
  }

  const st = STATUS[detail.status] || { label: detail.status, color: "default" };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Breadcrumb
        items={[
          { title: <Link to="/portal">总览</Link> },
          { title: <Link to="/portal/circuits">我的专线</Link> },
          { title: detail.code },
        ]}
      />

      <Card title={`${detail.name} · ${detail.code}`}>
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
          <Descriptions.Item label="状态">
            <Tag color={st.color}>{st.label}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="签约带宽">
            <Typography.Text strong>{detail.bandwidth_mbps} Mbps</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="SLA">{detail.sla_target || "—"}</Descriptions.Item>
          <Descriptions.Item label="VNI">{detail.vni ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="VSI">{detail.vsi_name || "—"}</Descriptions.Item>
          <Descriptions.Item label="业务类型">{detail.service_type}</Descriptions.Item>
          {detail.description ? (
            <Descriptions.Item label="描述" span={3}>
              {detail.description}
            </Descriptions.Item>
          ) : null}
        </Descriptions>
      </Card>

      <Card title="接入端点" size="small">
        <Descriptions column={1} size="small" bordered>
          {detail.endpoints.map((ep) => (
            <Descriptions.Item key={ep.label} label={`端点 ${ep.label}`}>
              {ep.interface_name}
              {ep.interface_description ? ` · ${ep.interface_description}` : ""}
              {ep.vlan_id ? ` · S-VID ${ep.vlan_id}` : ""}
              {ep.access_mode ? ` · ${ep.access_mode}` : ""}
            </Descriptions.Item>
          ))}
        </Descriptions>
      </Card>

      {(detail.status === "active" || detail.status === "degraded") && (
        <Card title="流量 · 带宽 · 95 计费">
          <PortalCircuitMonitorPanel circuitId={circuitId} />
        </Card>
      )}
    </div>
  );
}

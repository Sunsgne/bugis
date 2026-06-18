import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Breadcrumb, Card, Descriptions, Empty, Spin, Tag, Typography } from "antd";
import { api } from "../api/client";
import PortalCircuitMonitorPanel from "../components/PortalCircuitMonitorPanel";
import { CIRCUIT_STATUS, SERVICE_TYPE, statusMeta } from "../constants/statusLabels";
import { useTc } from "@/i18n/useTc";

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
  latency_probe_enabled?: boolean;
  endpoints: {
    label: string;
    interface_name: string;
    access_mode?: string;
    vlan_id?: number;
    interface_description?: string;
  }[];
}

export default function PortalCircuitDetail() {
  const { tc } = useTc();
  const { id } = useParams();
  const circuitId = Number(id);
  const validId = Number.isFinite(circuitId) && circuitId > 0;
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!validId) {
      setLoading(false);
      setError(true);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(false);
    api
      .get<Detail>(`/portal/circuits/${circuitId}`)
      .then((r) => {
        if (!cancelled) setDetail(r.data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [circuitId, validId]);

  if (loading) {
    return <Spin style={{ display: "block", margin: "80px auto" }} />;
  }

  if (error || !detail) {
    return (
      <Empty
        style={{ marginTop: 80 }}
        description={error ? "未找到该专线或无访问权限" : "暂无数据"}
      >
        <Link to="/portal/circuits">{tc('返回我的专线')}</Link>
      </Empty>
    );
  }

  const st = statusMeta(CIRCUIT_STATUS, detail.status);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Breadcrumb
        items={[
          { title: <Link to="/portal">{tc('总览')}</Link> },
          { title: <Link to="/portal/circuits">{tc('我的专线')}</Link> },
          { title: detail.code },
        ]}
      />

      <Card title={`${detail.name} · ${detail.code}`}>
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
          <Descriptions.Item label={tc('状态')}>
            <Tag color={st.color}>{st.label}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label={tc('签约带宽')}>
            <Typography.Text strong>{detail.bandwidth_mbps} Mbps</Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="SLA">{detail.sla_target || "—"}</Descriptions.Item>
          <Descriptions.Item label="VNI">{detail.vni ?? "—"}</Descriptions.Item>
          <Descriptions.Item label="VSI">{detail.vsi_name || "—"}</Descriptions.Item>
          <Descriptions.Item label={tc('业务类型')}>
            {SERVICE_TYPE[detail.service_type] || detail.service_type}
          </Descriptions.Item>
          {detail.description ? (
            <Descriptions.Item label={tc('描述')} span={3}>
              {detail.description}
            </Descriptions.Item>
          ) : null}
        </Descriptions>
      </Card>

      <Card title={tc('接入端点')} size="small">
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
        <Card title={tc('流量 · 带宽 · 95 计费')}>
          <PortalCircuitMonitorPanel
            circuitId={circuitId}
            latencyProbeEnabled={detail.latency_probe_enabled !== false}
          />
        </Card>
      )}
    </div>
  );
}

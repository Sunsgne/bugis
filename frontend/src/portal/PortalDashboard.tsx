import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Col, Row, Spin, Statistic, Table, Tag, Typography } from "antd";
import { api } from "../api/client";
import type { PortalMe } from "./PortalApp";

const STATUS: Record<string, { label: string; color: string }> = {
  active: { label: "运行中", color: "green" },
  degraded: { label: "降级", color: "orange" },
  provisioning: { label: "开通中", color: "processing" },
  draft: { label: "草稿", color: "default" },
  suspended: { label: "暂停", color: "volcano" },
  failed: { label: "失败", color: "red" },
};

interface DashboardData {
  summary: {
    circuits_total: number;
    circuits_active: number;
    active_bandwidth_mbps: number;
    total_bandwidth_mbps: number;
  };
  active_alarms: number;
  avg_health_score: number;
  circuits_monitorable: number;
}

interface PortalCircuitRow {
  id: number;
  code: string;
  name: string;
  status: string;
  bandwidth_mbps: number;
  service_type: string;
}

export default function PortalDashboard({ me }: { me: PortalMe | null }) {
  const [dash, setDash] = useState<DashboardData | null>(null);
  const [circuits, setCircuits] = useState<PortalCircuitRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [d, c] = await Promise.all([
          api.get<DashboardData>("/portal/dashboard"),
          api.get<PortalCircuitRow[]>("/portal/circuits"),
        ]);
        setDash(d.data);
        setCircuits(c.data.slice(0, 8));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <Spin style={{ display: "block", margin: "80px auto" }} />;

  const s = dash?.summary;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <Typography.Title level={4} style={{ marginBottom: 4 }}>
          欢迎，{me?.tenant_name || "客户"}
        </Typography.Title>
        <Typography.Text type="secondary">
          在此查看贵司专线运行状态、签约带宽与流量 95 计费数据
        </Typography.Text>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="专线总数" value={s?.circuits_total ?? 0} suffix="条" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="运行中" value={s?.circuits_active ?? 0} suffix="条" valueStyle={{ color: "#52c41a" }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="签约带宽"
              value={s?.active_bandwidth_mbps ?? 0}
              suffix="Mbps"
              valueStyle={{ color: "#ff6600" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="健康指数" value={dash?.avg_health_score ?? 100} suffix="/ 100" />
          </Card>
        </Col>
      </Row>

      <Card
        title="我的专线"
        extra={
          <Link to="/portal/circuits">查看全部</Link>
        }
      >
        <Table
          size="small"
          rowKey="id"
          pagination={false}
          dataSource={circuits}
          locale={{ emptyText: "暂无专线，请联系运营商开通" }}
          columns={[
            {
              title: "编码",
              dataIndex: "code",
              render: (code: string, row) => (
                <Link to={`/portal/circuits/${row.id}`}>{code}</Link>
              ),
            },
            { title: "名称", dataIndex: "name", ellipsis: true },
            {
              title: "带宽",
              dataIndex: "bandwidth_mbps",
              render: (v: number) => `${v} Mbps`,
            },
            {
              title: "状态",
              dataIndex: "status",
              render: (st: string) => {
                const m = STATUS[st] || { label: st, color: "default" };
                return <Tag color={m.color}>{m.label}</Tag>;
              },
            },
            {
              title: "",
              width: 88,
              render: (_: unknown, row) => (
                <Link to={`/portal/traffic?circuit=${row.id}`}>流量</Link>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}

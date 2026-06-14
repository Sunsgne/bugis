import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Spin, Tag, Empty } from "antd";
import {
  TeamOutlined,
  ClusterOutlined,
  ApiOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { api } from "../api/client";
import type { Dashboard as DashboardData } from "../api/types";

const VENDOR_COLORS: Record<string, string> = {
  h3c: "#1677ff",
  huawei: "#cf1322",
  juniper: "#52c41a",
  arista: "#fa8c16",
  cisco: "#722ed1",
  frr: "#13c2c2",
};
const STATUS_COLORS: Record<string, string> = {
  active: "#52c41a",
  draft: "#8c8c8c",
  provisioning: "#1677ff",
  failed: "#cf1322",
  degraded: "#fa8c16",
  decommissioned: "#bfbfbf",
};

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);

  async function load() {
    const { data } = await api.get<DashboardData>("/telemetry/dashboard");
    setData(data);
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  if (!data) return <Spin />;

  const vendorData = Object.entries(data.devices_by_vendor).map(([name, value]) => ({
    name,
    value,
  }));
  const statusData = Object.entries(data.circuits_by_status).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Row gutter={16}>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="租户总数" value={data.tenants} prefix={<TeamOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="设备 (在线/总数)"
              value={data.devices_online}
              suffix={`/ ${data.devices}`}
              prefix={<ClusterOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="专线 (活跃/总数)"
              value={data.circuits_active}
              suffix={`/ ${data.circuits}`}
              prefix={<ApiOutlined />}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="活跃带宽"
              value={data.total_active_bandwidth_mbps}
              suffix="Mbps"
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: "#1677ff" }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="设备厂商分布">
            {vendorData.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={vendorData}
                    dataKey="value"
                    nameKey="name"
                    outerRadius={100}
                    label
                  >
                    {vendorData.map((d) => (
                      <Cell key={d.name} fill={VENDOR_COLORS[d.name] || "#999"} />
                    ))}
                  </Pie>
                  <Legend />
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Empty />
            )}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="专线状态分布">
            {statusData.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={statusData}>
                  <XAxis dataKey="name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="value">
                    {statusData.map((d) => (
                      <Cell key={d.name} fill={STATUS_COLORS[d.name] || "#1677ff"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty />
            )}
          </Card>
        </Col>
      </Row>

      <Card size="small">
        <Tag color="blue">EVPN VXLAN: 华三 / 华为</Tag>
        <Tag color="purple">SR-MPLS EVPN: Juniper / Arista / Cisco</Tag>
        <Tag color="green">DCI 数据中心互联</Tag>
        <Tag color="orange">多租户混合云接入</Tag>
      </Card>
    </div>
  );
}

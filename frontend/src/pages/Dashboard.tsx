import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Spin, Tag, Empty, Progress, Table, Badge } from "antd";
import {
  TeamOutlined,
  ClusterOutlined,
  ApiOutlined,
  ThunderboltOutlined,
  AlertOutlined,
  ShareAltOutlined,
  NodeIndexOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import {
  Area,
  AreaChart,
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
  CartesianGrid,
} from "recharts";
import { api } from "../api/client";
import type { Dashboard as DashboardData } from "../api/types";
import { brand, empty } from "../constants/uiCopy";

const VENDOR_COLORS: Record<string, string> = {
  h3c: "#1677ff", huawei: "#cf1322", juniper: "#52c41a",
  arista: "#fa8c16", cisco: "#722ed1", frr: "#13c2c2",
};
const STATUS_COLORS: Record<string, string> = {
  active: "#52c41a", draft: "#8c8c8c", provisioning: "#1677ff",
  failed: "#cf1322", degraded: "#fa8c16", decommissioned: "#bfbfbf",
};
const SEV_COLORS: Record<string, string> = {
  critical: "#cf1322", major: "#fa541c", minor: "#fa8c16",
  warning: "#faad14", info: "#1677ff",
};
const WO_STATUS: Record<string, string> = {
  completed: "green", failed: "red", running: "processing",
  approved: "blue", submitted: "gold", draft: "default",
};

function utilColor(p: number) {
  return p >= 85 ? "#cf1322" : p >= 60 ? "#fa8c16" : "#52c41a";
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [traffic, setTraffic] = useState<any[]>([]);
  const [alarms, setAlarms] = useState<any>(null);
  const [sdn, setSdn] = useState<any>(null);
  const [sites, setSites] = useState<any[]>([]);
  const [links, setLinks] = useState<any[]>([]);
  const [wos, setWos] = useState<any[]>([]);
  const [sched, setSched] = useState<any>(null);

  async function load() {
    const safe = (p: Promise<any>, d: any) => p.then((r) => r.data).catch(() => d);
    const [d, tr, al, sd, si, li, wo, sy] = await Promise.all([
      safe(api.get("/telemetry/dashboard"), null),
      safe(api.get("/telemetry/overview"), []),
      safe(api.get("/alarms/summary"), { active: 0, by_severity: {} }),
      safe(api.get("/controller/status"), null),
      safe(api.get("/capacity/sites"), []),
      safe(api.get("/capacity/links/usage"), []),
      safe(api.get("/work-orders"), []),
      safe(api.get("/system/info"), null),
    ]);
    setData(d); setTraffic(tr); setAlarms(al); setSdn(sd);
    setSites(si); setLinks(li); setWos(wo.slice(0, 6)); setSched(sy?.scheduler);
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  if (!data) return <Spin size="large" style={{ display: "block", margin: "80px auto" }} />;

  const vendorData = Object.entries(data.devices_by_vendor).map(([name, value]) => ({ name, value }));
  const statusData = Object.entries(data.circuits_by_status).map(([name, value]) => ({ name, value }));
  const sevData = Object.entries(alarms?.by_severity || {}).map(([name, value]) => ({ name, value: value as number }));
  const totalCap = sites.reduce((a, s) => a + s.capacity_mbps, 0);
  const usedCap = sites.reduce((a, s) => a + s.used_mbps, 0);

  const kpi = (icon: any, title: string, value: any, suffix?: string, color?: string) => (
    <Card styles={{ body: { padding: 16 } }}>
      <Statistic title={title} value={value} suffix={suffix} prefix={icon}
        valueStyle={color ? { color } : undefined} />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Hero banner */}
      <div
        style={{
          background: "linear-gradient(120deg, #0b1f3a 0%, #1668dc 60%, #13c2c2 100%)",
          borderRadius: 12, padding: "20px 28px", color: "#fff",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          flexWrap: "wrap", gap: 16,
          boxShadow: "0 8px 24px rgba(11,31,58,0.25)",
        }}
      >
        <div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{brand.heroTitle}</div>
          <div style={{ opacity: 0.85, marginTop: 4 }}>
            {brand.heroSubtitle}
          </div>
          <div style={{ marginTop: 10 }}>
            <Badge status={sched?.running ? "processing" : "default"} />
            <span style={{ opacity: 0.9 }}>
              {sched?.running ? `巡检引擎运行中 · ${sched.ticks} 次 · 周期 ${sched.interval}s` : "巡检引擎待机"}
            </span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
          {[
            { l: "在网专线", v: data.circuits_active },
            { l: "在网带宽", v: `${(data.total_active_bandwidth_mbps / 1000).toFixed(1)}G` },
            { l: "在线设备", v: data.devices_online },
            { l: "活跃告警", v: alarms?.active || 0, warn: (alarms?.active || 0) > 0 },
          ].map((m) => (
            <div key={m.l} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 30, fontWeight: 700, color: m.warn ? "#ffccc7" : "#fff" }}>{m.v}</div>
              <div style={{ opacity: 0.85, fontSize: 13 }}>{m.l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* KPI cards */}
      <Row gutter={[16, 16]}>
        <Col xs={12} md={4}>{kpi(<TeamOutlined />, "客户租户", data.tenants)}</Col>
        <Col xs={12} md={4}>{kpi(<ClusterOutlined />, "设备 · 在线/总量", data.devices_online, `/ ${data.devices}`)}</Col>
        <Col xs={12} md={4}>{kpi(<ApiOutlined />, "在网专线 · 活跃/总量", data.circuits_active, `/ ${data.circuits}`, "#52c41a")}</Col>
        <Col xs={12} md={4}>{kpi(<ThunderboltOutlined />, "在网带宽 (Mbps)", data.total_active_bandwidth_mbps, undefined, "#1677ff")}</Col>
        <Col xs={12} md={4}>{kpi(<NodeIndexOutlined />, "EVPN 路由条目", sdn?.route_count ?? 0, undefined, "#722ed1")}</Col>
        <Col xs={12} md={4}>{kpi(<AlertOutlined />, "活跃告警", alarms?.active || 0, undefined, (alarms?.active || 0) > 0 ? "#cf1322" : "#52c41a")}</Col>
      </Row>

      {/* Traffic trend + alarm donut */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="全网流量态势 · Rx/Tx 聚合 (Mbps)" style={{ height: "100%" }}>
            {traffic.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={traffic}>
                  <defs>
                    <linearGradient id="rx" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#1677ff" stopOpacity={0.5} />
                      <stop offset="95%" stopColor="#1677ff" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="tx" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#52c41a" stopOpacity={0.5} />
                      <stop offset="95%" stopColor="#52c41a" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="t" /><YAxis /><Tooltip /><Legend />
                  <Area type="monotone" dataKey="rx" stroke="#1677ff" fill="url(#rx)" name="Rx" />
                  <Area type="monotone" dataKey="tx" stroke="#52c41a" fill="url(#tx)" name="Tx" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <Empty description={empty.traffic} style={{ padding: 60 }} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="告警态势 · 按严重级别" style={{ height: "100%" }}>
            {sevData.length ? (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={sevData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} label>
                    {sevData.map((d) => <Cell key={d.name} fill={SEV_COLORS[d.name] || "#999"} />)}
                  </Pie>
                  <Legend /><Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: "center", padding: "70px 0" }}>
                <SafetyCertificateOutlined style={{ fontSize: 56, color: "#52c41a" }} />
                <div style={{ marginTop: 12, color: "#52c41a", fontSize: 16 }}>{empty.alarms}</div>
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* Vendor / status / SDN */}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card title="设备厂商 · 异构分布" style={{ height: "100%" }}>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={vendorData} dataKey="value" nameKey="name" outerRadius={90} label>
                  {vendorData.map((d) => <Cell key={d.name} fill={VENDOR_COLORS[d.name] || "#999"} />)}
                </Pie>
                <Legend /><Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="专线生命周期 · 状态分布" style={{ height: "100%" }}>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={statusData}>
                <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip />
                <Bar dataKey="value">
                  {statusData.map((d) => <Cell key={d.name} fill={STATUS_COLORS[d.name] || "#1677ff"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="SDN 控制面 · Bugis Controller" style={{ height: "100%" }}
            extra={<Tag color="green">{sdn?.name ? "在线" : "—"}</Tag>}>
            <Row gutter={16}>
              <Col span={8}><Statistic title="VTEP" value={sdn?.vtep_count ?? 0} prefix={<ShareAltOutlined />} /></Col>
              <Col span={8}><Statistic title="EVPN 路由" value={sdn?.route_count ?? 0} /></Col>
              <Col span={8}><Statistic title="VNI" value={sdn?.vni_count ?? 0} /></Col>
            </Row>
            <div style={{ marginTop: 16 }}>
              {Object.entries(sdn?.routes_by_type || {}).map(([k, v]: any) => (
                <Tag key={k} color="purple" style={{ marginBottom: 6 }}>
                  {k.replace("type3_imet", "Type-3 IMET").replace("type2_mac_ip", "Type-2 MAC/IP").replace("type5_ip_prefix", "Type-5 前缀")}: {v}
                </Tag>
              ))}
              {!sdn && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty.data} />}
            </div>
          </Card>
        </Col>
      </Row>

      {/* Capacity + recent work orders */}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card title="Fabric 容量 · 站点分配" style={{ height: "100%" }}>
            <div style={{ marginBottom: 12 }}>
              <span style={{ color: "#888" }}>全域分配率</span>
              <Progress percent={totalCap ? Math.round((usedCap / totalCap) * 1000) / 10 : 0}
                strokeColor={utilColor(totalCap ? (usedCap / totalCap) * 100 : 0)} />
            </div>
            {sites.map((s) => (
              <div key={s.site_id} style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                  <span>{s.code} · {s.site}</span>
                  <span style={{ color: "#888" }}>{Math.round(s.used_mbps / 1000)}/{Math.round(s.capacity_mbps / 1000)}G</span>
                </div>
                <Progress percent={s.utilization_pct} size="small" strokeColor={utilColor(s.utilization_pct)} />
              </div>
            ))}
            {!sites.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty.data} />}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="链路负载 · DCI / Fabric" style={{ height: "100%" }}>
            {links.map((l) => (
              <div key={l.link_id} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                  <span><Tag color={l.type === "dci" ? "red" : "blue"} style={{ marginRight: 4 }}>{l.type}</Tag>{l.name}</span>
                  <span style={{ color: "#888" }}>{Math.round(l.capacity_mbps / 1000)}G</span>
                </div>
                <Progress percent={l.utilization_pct} size="small" strokeColor={utilColor(l.utilization_pct)} />
              </div>
            ))}
            {!links.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty.data} />}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="编排工单 · 最近动态" style={{ height: "100%" }}>
            <Table
              size="small"
              rowKey="id"
              pagination={false}
              dataSource={wos}
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
              columns={[
                { title: "工单", dataIndex: "code", width: 110 },
                { title: "类型", dataIndex: "type", render: (t) => <Tag>{t}</Tag> },
                { title: "状态", dataIndex: "status", render: (s) => <Tag color={WO_STATUS[s]}>{s}</Tag> },
                { title: "时间", dataIndex: "created_at", render: (t) => (t ? dayjs(t).format("MM-DD HH:mm") : "-") },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

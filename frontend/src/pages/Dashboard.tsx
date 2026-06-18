import { useEffect, useMemo, useState } from "react";
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
import { api } from "../api/client";
import type { Dashboard as DashboardData } from "../api/types";
import EChart from "../components/EChart";
import {
  donutOption,
  gradientBarOption,
  rosePieOption,
  severityColors,
  statusColors,
  trafficAreaOption,
  utilColor,
  vendorColors,
} from "../charts/options";
import { empty } from "../constants/uiCopy";
import { useBrand } from "../context/BrandContext";
import { useTc } from "@/i18n/useTc";
import { useUserDatetime } from "@/utils/datetime";

const WO_STATUS: Record<string, string> = {
  completed: "green", failed: "red", running: "processing",
  approved: "blue", submitted: "gold", draft: "default",
};

export default function Dashboard() {
  const { tc } = useTc();
  const { timezone, formatShort, mapTrafficLabels } = useUserDatetime();
  const { brand } = useBrand();
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

  const vendorData = useMemo(
    () => Object.entries(data?.devices_by_vendor ?? {}).map(([name, value]) => ({ name, value: value as number })),
    [data],
  );
  const statusData = useMemo(
    () => Object.entries(data?.circuits_by_status ?? {}).map(([name, value]) => ({ name, value: value as number })),
    [data],
  );
  const sevData = useMemo(
    () => Object.entries(alarms?.by_severity || {}).map(([name, value]) => ({ name, value: value as number })),
    [alarms],
  );

  const trafficOpt = useMemo(
    () => trafficAreaOption(mapTrafficLabels(traffic, 3), "t"),
    [traffic, timezone, mapTrafficLabels],
  );
  const alarmOpt = useMemo(() => donutOption(sevData, severityColors, "告警"), [sevData]);
  const vendorOpt = useMemo(() => rosePieOption(vendorData, vendorColors), [vendorData]);
  const statusOpt = useMemo(() => gradientBarOption(statusData, statusColors), [statusData]);

  if (!data) return <Spin size="large" style={{ display: "block", margin: "80px auto" }} />;

  const totalCap = sites.reduce((a, s) => a + s.capacity_mbps, 0);
  const usedCap = sites.reduce((a, s) => a + s.used_mbps, 0);

  const kpi = (icon: any, title: string, value: any, suffix?: string, color?: string) => (
    <Card className="chart-card" styles={{ body: { padding: 16 } }}>
      <Statistic title={title} value={value} suffix={suffix} prefix={icon}
        valueStyle={color ? { color } : undefined} />
    </Card>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div
        className="dashboard-hero-banner"
        style={{
          background: "linear-gradient(120deg, #2a1303 0%, #d24e00 55%, #ff7a1a 100%)",
          boxShadow: "0 8px 24px rgba(210,78,0,0.28)",
        }}
      >
        <div className="dashboard-hero-copy">
          <div className="dashboard-hero-title">{brand.hero_title}</div>
          <div className="dashboard-hero-subtitle">{brand.hero_subtitle}</div>
          <div className="dashboard-hero-status">
            <span className="dashboard-hero-status-pill">
              <Badge status={sched?.running ? "processing" : "default"} />
              <span>{sched?.running ? "巡检引擎运行中" : "巡检引擎待机"}</span>
            </span>
            {sched?.running ? (
              <>
                <span className="dashboard-hero-status-metric">已执行 {sched.ticks ?? 0} 次</span>
                <span className="dashboard-hero-status-metric">周期 {sched.interval ?? "—"}s</span>
                {sched.last_learn_devices != null && sched.last_learn_devices > 0 ? (
                  <span className="dashboard-hero-status-metric">
                    自学习 {sched.last_learn_devices} 台
                  </span>
                ) : null}
              </>
            ) : null}
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

      <Row gutter={[16, 16]}>
        <Col xs={12} md={4}>{kpi(<TeamOutlined />, "客户", data.tenants)}</Col>
        <Col xs={12} md={4}>{kpi(<ClusterOutlined />, "设备 · 在线/总量", data.devices_online, `/ ${data.devices}`)}</Col>
        <Col xs={12} md={4}>{kpi(<ApiOutlined />, "在网专线 · 活跃/总量", data.circuits_active, `/ ${data.circuits}`, "#52c41a")}</Col>
        <Col xs={12} md={4}>{kpi(<ThunderboltOutlined />, "在网带宽 (Mbps)", data.total_active_bandwidth_mbps, undefined, "#ff6600")}</Col>
        <Col xs={12} md={4}>{kpi(<NodeIndexOutlined />, "EVPN 路由条目", sdn?.route_count ?? 0, undefined, "#722ed1")}</Col>
        <Col xs={12} md={4}>{kpi(<AlertOutlined />, "活跃告警", alarms?.active || 0, undefined, (alarms?.active || 0) > 0 ? "#cf1322" : "#52c41a")}</Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card className="chart-card" title={tc('全网流量态势 · Rx/Tx 聚合 (Mbps)')} style={{ height: "100%" }}>
            {traffic.length ? (
              <EChart option={trafficOpt} height={300} />
            ) : (
              <Empty description={empty.traffic} style={{ padding: 60 }} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card className="chart-card" title={tc('告警态势 · 按严重级别')} style={{ height: "100%" }}>
            {sevData.length ? (
              <EChart option={alarmOpt} height={300} />
            ) : (
              <div style={{ textAlign: "center", padding: "70px 0" }}>
                <SafetyCertificateOutlined style={{ fontSize: 56, color: "#52c41a" }} />
                <div style={{ marginTop: 12, color: "#52c41a", fontSize: 16 }}>{empty.alarms}</div>
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card className="chart-card" title={tc('设备厂商 · 异构分布')} style={{ height: "100%" }}>
            {vendorData.length ? (
              <EChart option={vendorOpt} height={260} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty.data} style={{ padding: 48 }} />
            )}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="chart-card" title={tc('专线生命周期 · 状态分布')} style={{ height: "100%" }}>
            {statusData.length ? (
              <EChart option={statusOpt} height={260} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty.data} style={{ padding: 48 }} />
            )}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="chart-card" title={tc('SDN 控制面 · Bugis Controller')} style={{ height: "100%" }}
            extra={<Tag color="green">{sdn?.name ? "在线" : "—"}</Tag>}>
            <Row gutter={16}>
              <Col span={8}><Statistic title="VTEP" value={sdn?.vtep_count ?? 0} prefix={<ShareAltOutlined />} /></Col>
              <Col span={8}><Statistic title={tc('EVPN 路由')} value={sdn?.route_count ?? 0} /></Col>
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

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card className="chart-card" title={tc('Fabric 容量 · 站点分配')} style={{ height: "100%" }}>
            <div style={{ marginBottom: 12 }}>
              <span style={{ color: "#888" }}>{tc('全域分配率')}</span>
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
          <Card className="chart-card" title={tc('链路负载 · DCI / Fabric')} style={{ height: "100%" }}>
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
          <Card className="chart-card" title={tc('操作日志 · 最近动态')} style={{ height: "100%" }}>
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
                { title: "时间", dataIndex: "created_at", render: (t) => (t ? formatShort(t) : "-") },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

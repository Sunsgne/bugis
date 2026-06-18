import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Card,
  Col,
  Row,
  Statistic,
  Table,
  Tag,
  Select,
  Empty,
  Descriptions,
  Typography,
  Button,
  message,
  Space,
  Spin,
} from "antd";
import {
  ClusterOutlined,
  NodeIndexOutlined,
  ShareAltOutlined,
  ApiOutlined,
  CloudServerOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import OverlayTopologyPanel from "../components/OverlayTopologyPanel";
import { empty, page } from "../constants/uiCopy";

const { Text } = Typography;

function OverlayScanSummary({ overlay }: { overlay: any }) {
  const items: any[] = Array.isArray(overlay?.items) ? overlay.items : [];
  const platform = overlay?.platform_services ?? 0;
  const networkOnly = overlay?.network_only_services ?? 0;
  const scanned = overlay?.devices_scanned ?? 0;
  const withInventory = overlay?.devices_with_inventory ?? 0;
  const reserved = overlay?.reserved_vni_count ?? 0;

  // Per-device service distribution — a summary the table (one row per service)
  // does not show directly, so it complements rather than duplicates the table.
  const deviceDist = useMemo(() => {
    const counts = new Map<string, number>();
    for (const it of items) {
      const name = it?.device || "—";
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([device, count]) => ({ device, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }, [items]);
  const maxCount = deviceDist.length ? deviceDist[0].count : 0;

  return (
    <div
      style={{
        background: "#fafafa",
        border: "1px solid #f0f0f0",
        borderRadius: 8,
        padding: 16,
        height: "100%",
      }}
    >
      <Text strong>扫描摘要</Text>
      <Row gutter={[8, 8]} style={{ marginTop: 12 }}>
        <Col span={12}>
          <Statistic title="平台纳管" value={platform} valueStyle={{ color: "#ff6600" }} />
        </Col>
        <Col span={12}>
          <Statistic title="现网未纳管" value={networkOnly} valueStyle={{ color: "#fa8c16" }} />
        </Col>
        <Col span={12}>
          <Statistic title="已扫描设备" value={`${withInventory}/${scanned}`} />
        </Col>
        <Col span={12}>
          <Statistic title="保留 VNI" value={reserved} prefix={<CloudServerOutlined />} />
        </Col>
      </Row>

      <div style={{ marginTop: 16 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          按设备占用分布 Top
        </Text>
        <div style={{ marginTop: 8, minHeight: 32 }}>
          {deviceDist.length ? (
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              {deviceDist.map((d) => (
                <div key={d.device}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 12,
                      marginBottom: 2,
                    }}
                  >
                    <Text ellipsis style={{ maxWidth: 200 }} title={d.device}>
                      {d.device}
                    </Text>
                    <Text type="secondary">{d.count}</Text>
                  </div>
                  <div style={{ background: "#f0f0f0", borderRadius: 3, height: 6 }}>
                    <div
                      style={{
                        width: `${maxCount ? (d.count / maxCount) * 100 : 0}%`,
                        background: "#ff6600",
                        height: 6,
                        borderRadius: 3,
                      }}
                    />
                  </div>
                </div>
              ))}
            </Space>
          ) : (
            <Text type="secondary" style={{ fontSize: 12 }}>
              暂无现网占用记录
            </Text>
          )}
        </div>
      </div>

      <Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: 16 }}>
        只读扫描 learned running-config，不会下发或修改设备配置；新建专线自动避开已占用 VNI/VSI。
      </Text>
    </div>
  );
}

const RT_LABEL: Record<string, string> = {
  type3_imet: "Type-3 IMET",
  type2_mac_ip: "Type-2 MAC/IP",
  type5_ip_prefix: "Type-5 IP前缀",
  type4_es: "Type-4 ES",
};
const RT_COLOR: Record<string, string> = {
  type3_imet: "blue",
  type2_mac_ip: "green",
  type5_ip_prefix: "purple",
  type4_es: "orange",
};

const BGP_COLOR: Record<string, string> = {
  established: "green",
  connect: "blue",
  idle: "default",
};

const DP_COLOR: Record<string, string> = {
  applied: "green",
  rendered: "blue",
  pending: "orange",
  failed: "red",
};

export default function ControlPlane() {
  const [status, setStatus] = useState<any>(null);
  const [vteps, setVteps] = useState<any[]>([]);
  const [routes, setRoutes] = useState<any[]>([]);
  const [topo, setTopo] = useState<any>(null);
  const [bgp, setBgp] = useState<any[]>([]);
  const [cluster, setCluster] = useState<any>(null);
  const [bindings, setBindings] = useState<any[]>([]);
  const [overlay, setOverlay] = useState<any>(null);
  const [vni, setVni] = useState<number | undefined>(undefined);
  const [syncing, setSyncing] = useState(false);
  const [scanningOverlay, setScanningOverlay] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  async function load() {
    try {
      const [s, v, r, t, b, c, d, o] = await Promise.all([
        api.get("/controller/status"),
        api.get("/controller/vteps"),
        api.get("/controller/routes" + (vni != null ? `?vni=${vni}` : "")),
        api.get("/controller/topology"),
        api.get("/controller/bgp/sessions"),
        api.get("/controller/cluster"),
        api.get("/controller/dataplane/bindings"),
        api.get("/controller/overlay-inventory"),
      ]);
      setStatus(s.data);
      setVteps(Array.isArray(v.data) ? v.data : []);
      setRoutes(Array.isArray(r.data) ? r.data : []);
      setTopo(t.data ?? { nodes: [], edges: [], vnis: [] });
      setBgp(Array.isArray(b.data) ? b.data : []);
      setCluster(c.data);
      setBindings(Array.isArray(d.data) ? d.data : []);
      setOverlay(o.data);
      setLoadError(null);
    } catch (e: any) {
      setLoadError(e?.response?.data?.detail || e?.message || "加载控制器数据失败");
    } finally {
      setLoaded(true);
    }
  }

  async function syncBgp() {
    setSyncing(true);
    try {
      await api.post("/controller/bgp/sync");
      message.success("BGP 会话已同步");
      load();
    } finally {
      setSyncing(false);
    }
  }

  async function scanOverlay() {
    setScanningOverlay(true);
    try {
      const { data } = await api.post("/controller/overlay-inventory/scan");
      setOverlay(data);
      const cleaned = data.stale_vni_removed ?? 0;
      message.success(
        `现网扫描完成 · ${data.network_only_services ?? 0} 个未纳管服务 · 保留 ${data.reserved_vni_count ?? 0} 个 VNI` +
          (cleaned > 0 ? ` · 已清理 ${cleaned} 条陈旧拓扑` : ""),
      );
      // Refresh topology / VTEPs so the graph reflects the reconciled state.
      load();
    } finally {
      setScanningOverlay(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [vni]);

  const allVnis = Array.from(new Set(vteps.flatMap((v) => v.vnis ?? []))).sort((a, b) => a - b);

  if (!loaded && !loadError) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "80px 0" }}>
        <Spin />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {loadError && (
        <Card size="small">
          <Text type="danger">{loadError}</Text>
        </Card>
      )}
      <Card>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <span style={{ fontSize: 16, fontWeight: 600 }}>
              <ShareAltOutlined /> {status?.name || "Bugis SDN 控制器"}
            </span>
            <Tag color="geekblue" style={{ marginLeft: 8 }}>内置 · 自研 SDN</Tag>
            {status?.version && <Tag style={{ marginLeft: 4 }}>v{status.version}</Tag>}
          </Col>
          <Col>
            <Button loading={syncing} onClick={syncBgp}>
              同步 BGP 会话
            </Button>
          </Col>
        </Row>
        <Descriptions size="small" style={{ marginTop: 16 }} column={{ xs: 1, sm: 2, md: 4 }}>
          <Descriptions.Item label="RIB 版本">v{status?.rib_version ?? 0}</Descriptions.Item>
          <Descriptions.Item label="BGP 会话在线">{status?.bgp_sessions_up ?? 0}</Descriptions.Item>
          <Descriptions.Item label="集群模式">{cluster?.mode || "-"}</Descriptions.Item>
          <Descriptions.Item label="Leader">{cluster?.leader || "-"}</Descriptions.Item>
          <Descriptions.Item label="配置版本化">
              设备配置见 <Link to="/config">{page.config}</Link>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Row gutter={16}>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="VTEP 节点" value={status?.vtep_count || 0} prefix={<ClusterOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="EVPN 路由" value={status?.route_count || 0} prefix={<NodeIndexOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="BGP 会话"
              value={status?.bgp_sessions_up || 0}
              suffix={`/ ${bgp.length}`}
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="现网保留 VNI"
              value={overlay?.reserved_vni_count ?? 0}
              suffix={overlay?.smart_allocation_enabled ? "智能避让" : ""}
              prefix={<CloudServerOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="现网 VNI / VSI 占用扫描"
        size="small"
        extra={
          <Button loading={scanningOverlay} onClick={scanOverlay}>
            扫描现网标识
          </Button>
        }
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={16}>
            <Table
              rowKey={(row: { device_id?: number; service_name?: string; vni?: number }) =>
                `${row.device_id}-${row.service_name}-${row.vni ?? "u"}`
              }
              dataSource={(overlay?.items ?? []).slice(0, 100)}
              pagination={{ pageSize: 20, showSizeChanger: true }}
              size="small"
              scroll={{ x: "max-content" }}
              locale={{ emptyText: <Empty description="暂无现网 Overlay 数据 · 请对设备执行现网学习后扫描" /> }}
              columns={[
                { title: "设备", dataIndex: "device", ellipsis: true },
                { title: "VSI / 服务", dataIndex: "service_name", ellipsis: true },
                { title: "VNI", dataIndex: "vni", width: 90 },
                { title: "RD", dataIndex: "rd", ellipsis: true },
                {
                  title: "来源",
                  dataIndex: "source",
                  width: 110,
                  render: (s: string) => (
                    <Tag color={s === "platform" ? "blue" : "orange"}>
                      {s === "platform" ? "平台纳管" : "现网占用"}
                    </Tag>
                  ),
                },
                {
                  title: "专线",
                  dataIndex: "circuit_code",
                  render: (code?: string) => code || "—",
                },
                {
                  title: "接入接口",
                  dataIndex: "interfaces",
                  render: (ifs: string[] | undefined) => (ifs?.length ? ifs.join(", ") : "—"),
                },
              ]}
            />
          </Col>
          <Col xs={24} xl={8}>
            <OverlayScanSummary overlay={overlay} />
          </Col>
        </Row>
      </Card>

      <Card title="控制器集群 · HA" size="small">
        <Table
          rowKey="node_id"
          dataSource={cluster?.nodes || []}
          pagination={false}
          size="small"
          locale={{ emptyText: <Empty description={empty.data} /> }}
          columns={[
            { title: "节点", dataIndex: "node_id" },
            { title: "主机", dataIndex: "hostname" },
            {
              title: "角色",
              dataIndex: "role",
              render: (r) => (
                <Tag color={r === "leader" ? "blue" : r === "standby" ? "purple" : "default"}>
                  {r}
                </Tag>
              ),
            },
            { title: "RIB 版本", dataIndex: "rib_version" },
            {
              title: "本机",
              dataIndex: "is_local",
              render: (v) => (v ? <Tag color="green">是</Tag> : "-"),
            },
            { title: "最近心跳", dataIndex: "last_heartbeat" },
          ]}
        />
      </Card>

      <Card title="BGP EVPN 对等会话" size="small">
        <Table
          rowKey="id"
          dataSource={bgp}
          pagination={false}
          size="small"
          locale={{ emptyText: <Empty description="托管专线开通后自动建立 BGP 对等" /> }}
          columns={[
            { title: "设备", dataIndex: "device_name" },
            { title: "对端 IP", dataIndex: "peer_ip" },
            { title: "本地 ASN", dataIndex: "local_asn" },
            { title: "对端 ASN", dataIndex: "remote_asn" },
            {
              title: "状态",
              dataIndex: "state",
              render: (s) => <Tag color={BGP_COLOR[s] || "default"}>{s}</Tag>,
            },
            { title: "收路由", dataIndex: "routes_received" },
            { title: "发路由", dataIndex: "routes_sent" },
          ]}
        />
      </Card>

      <Card title="数据面编排绑定" size="small">
        <Table
          rowKey="id"
          dataSource={bindings.slice(0, 50)}
          pagination={false}
          size="small"
          locale={{ emptyText: <Empty description="暂无数据面绑定记录" /> }}
          columns={[
            { title: "专线 ID", dataIndex: "circuit_id", width: 90 },
            { title: "设备 ID", dataIndex: "device_id", width: 90 },
            { title: "操作", dataIndex: "operation", width: 80 },
            { title: "传输", dataIndex: "transport", width: 90 },
            {
              title: "状态",
              dataIndex: "state",
              render: (s) => <Tag color={DP_COLOR[s] || "default"}>{s}</Tag>,
            },
            { title: "时间", dataIndex: "created_at" },
          ]}
        />
      </Card>

      <Card title="VXLAN / SR-MPLS Overlay">
        <OverlayTopologyPanel topo={topo} />
      </Card>

      <Card title="VTEP 邻居表">
        <Table
          rowKey="id"
          dataSource={vteps}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无 VTEP 邻居" /> }}
          columns={[
            { title: "设备", dataIndex: "name" },
            { title: "VTEP IP", dataIndex: "vtep_ip" },
            { title: "ASN", dataIndex: "asn" },
            {
              title: "状态",
              dataIndex: "status",
              render: (s) => <Tag color={s === "up" ? "green" : "red"}>{s}</Tag>,
            },
            {
              title: "VNI",
              dataIndex: "vnis",
              render: (vs: number[] | undefined) => (vs ?? []).map((v) => <Tag key={v}>{v}</Tag>),
            },
          ]}
        />
      </Card>

      <Card
        title="EVPN 路由表 (RIB)"
        extra={
          <Select
            allowClear
            placeholder="按 VNI 过滤"
            style={{ width: 160 }}
            value={vni}
            onChange={(v) => setVni(v)}
            options={allVnis.map((v) => ({ value: v, label: `VNI ${v}` }))}
          />
        }
      >
        <Table
          rowKey="id"
          dataSource={routes}
          size="small"
          locale={{ emptyText: <Empty description="RIB 为空 · 等待路由同步" /> }}
          columns={[
            {
              title: "类型",
              dataIndex: "type",
              render: (t) => <Tag color={RT_COLOR[t]}>{RT_LABEL[t] || t}</Tag>,
            },
            { title: "VNI", dataIndex: "vni", width: 70 },
            {
              title: "封装",
              dataIndex: "encap",
              width: 80,
              render: (e) => <Tag>{e || "vxlan"}</Tag>,
            },
            { title: "MPLS 标签", dataIndex: "mpls_label", render: (v) => v || "-" },
            { title: "RD", dataIndex: "rd" },
            { title: "下一跳", dataIndex: "next_hop" },
          ]}
        />
      </Card>
    </div>
  );
}

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
} from "antd";
import {
  ClusterOutlined,
  NodeIndexOutlined,
  ShareAltOutlined,
  ApiOutlined,
  CloudServerOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";

const VNI_COLORS = ["#1677ff", "#52c41a", "#fa8c16", "#722ed1", "#13c2c2", "#eb2f96"];

function OverlayMap({ topo }: { topo: any }) {
  const layout = useMemo(() => {
    if (!topo || !topo.nodes?.length) return null;
    const n = topo.nodes.length;
    const cx = 320;
    const cy = 220;
    const r = Math.min(170, 60 + n * 16);
    const pos: Record<number, { x: number; y: number }> = {};
    topo.nodes.forEach((node: any, i: number) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2;
      pos[node.id] = { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });
    return { pos, width: 640, height: 440 };
  }, [topo]);

  if (!topo || !topo.nodes?.length || !layout) {
    return <Empty description="暂无 Overlay，开通由本控制器托管的专线后出现" />;
  }
  const vniColor = (vni: number) =>
    VNI_COLORS[(topo.vnis.indexOf(vni) + VNI_COLORS.length) % VNI_COLORS.length];

  return (
    <div style={{ overflow: "auto" }}>
      <svg width={layout.width} height={layout.height} style={{ minWidth: "100%" }}>
        {topo.edges.map((e: any, i: number) => {
          const a = layout.pos[e.source];
          const b = layout.pos[e.target];
          if (!a || !b) return null;
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={vniColor(e.vni)}
              strokeWidth={1.5}
              strokeDasharray="5 4"
              opacity={0.6}
            />
          );
        })}
        {topo.nodes.map((node: any) => {
          const p = layout.pos[node.id];
          return (
            <g key={node.id}>
              <circle
                cx={p.x}
                cy={p.y}
                r={22}
                fill="#fff"
                stroke={node.status === "up" ? "#52c41a" : "#bfbfbf"}
                strokeWidth={3}
              />
              <text x={p.x} y={p.y + 4} fontSize={11} textAnchor="middle">
                VTEP
              </text>
              <text x={p.x} y={p.y - 30} fontSize={11} fontWeight={600} textAnchor="middle">
                {node.name}
              </text>
              <text x={p.x} y={p.y + 38} fontSize={10} fill="#888" textAnchor="middle">
                {node.vtep_ip}
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{ marginTop: 8 }}>
        {topo.vnis.map((v: number) => (
          <Tag key={v} color={vniColor(v)}>
            VNI {v}
          </Tag>
        ))}
      </div>
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
  const [vni, setVni] = useState<number | undefined>(undefined);
  const [syncing, setSyncing] = useState(false);

  async function load() {
    const [s, v, r, t, b, c, d] = await Promise.all([
      api.get("/controller/status"),
      api.get("/controller/vteps"),
      api.get("/controller/routes" + (vni != null ? `?vni=${vni}` : "")),
      api.get("/controller/topology"),
      api.get("/controller/bgp/sessions"),
      api.get("/controller/cluster"),
      api.get("/controller/dataplane/bindings"),
    ]);
    setStatus(s.data);
    setVteps(v.data);
    setRoutes(r.data);
    setTopo(t.data);
    setBgp(b.data);
    setCluster(c.data);
    setBindings(d.data);
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

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [vni]);

  const allVnis = Array.from(new Set(vteps.flatMap((v) => v.vnis))).sort((a, b) => a - b);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <span style={{ fontSize: 16, fontWeight: 600 }}>
              <ShareAltOutlined /> {status?.name || "Bugis SDN 控制器"}
            </span>
            <Tag color="geekblue" style={{ marginLeft: 8 }}>内置 · 自研</Tag>
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
            设备配置见 <Link to="/config">配置管理</Link>
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
              title="数据面绑定"
              value={bindings.filter((b) => b.state === "applied").length}
              suffix={`/ ${bindings.length}`}
              prefix={<CloudServerOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card title="控制器集群 (HA)" size="small">
        <Table
          rowKey="node_id"
          dataSource={cluster?.nodes || []}
          pagination={false}
          size="small"
          locale={{ emptyText: <Empty description="集群节点加载中" /> }}
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
          locale={{ emptyText: <Empty description="开通控制器托管专线后自动建立" /> }}
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
          locale={{ emptyText: <Empty description="暂无数据面绑定" /> }}
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

      <Card title="VXLAN / SR-MPLS Overlay 拓扑">
        <OverlayMap topo={topo} />
      </Card>

      <Card title="VTEP 邻居表">
        <Table
          rowKey="id"
          dataSource={vteps}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无 VTEP" /> }}
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
              render: (vs: number[]) => vs.map((v) => <Tag key={v}>{v}</Tag>),
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
          locale={{ emptyText: <Empty description="控制器 RIB 为空" /> }}
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

import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Table, Tag, Select, Empty } from "antd";
import { ClusterOutlined, NodeIndexOutlined, ShareAltOutlined } from "@ant-design/icons";
import { api } from "../api/client";

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

export default function ControlPlane() {
  const [status, setStatus] = useState<any>(null);
  const [vteps, setVteps] = useState<any[]>([]);
  const [routes, setRoutes] = useState<any[]>([]);
  const [vni, setVni] = useState<number | undefined>(undefined);

  async function load() {
    const [s, v, r] = await Promise.all([
      api.get("/controller/status"),
      api.get("/controller/vteps"),
      api.get("/controller/routes" + (vni != null ? `?vni=${vni}` : "")),
    ]);
    setStatus(s.data);
    setVteps(v.data);
    setRoutes(r.data);
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [vni]);

  const allVnis = Array.from(new Set(vteps.flatMap((v) => v.vnis))).sort(
    (a, b) => a - b
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <span style={{ fontSize: 16, fontWeight: 600 }}>
              <ShareAltOutlined /> {status?.name || "Bugis SDN 控制器"}
            </span>
            <Tag color="green" style={{ marginLeft: 8 }}>自研 · 非市售</Tag>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="VTEP 节点" value={status?.vtep_count || 0} prefix={<ClusterOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="VTEP 在线" value={status?.vteps_up || 0} valueStyle={{ color: "#52c41a" }} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="EVPN 路由" value={status?.route_count || 0} prefix={<NodeIndexOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="管理 VNI 数" value={status?.vni_count || 0} />
          </Card>
        </Col>
      </Row>

      <Card title="VTEP 邻居表 (Bugis 控制器视图)">
        <Table
          rowKey="id"
          dataSource={vteps}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无 VTEP，开通由本控制器托管的专线后出现" /> }}
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
              title: "路由类型",
              dataIndex: "type",
              render: (t) => <Tag color={RT_COLOR[t]}>{RT_LABEL[t] || t}</Tag>,
            },
            { title: "VNI", dataIndex: "vni" },
            { title: "RD", dataIndex: "rd" },
            { title: "RT", dataIndex: "rt" },
            { title: "MAC", dataIndex: "mac", render: (m) => m || "-" },
            { title: "IP", dataIndex: "ip", render: (i) => i || "-" },
            { title: "VTEP/下一跳", dataIndex: "next_hop" },
          ]}
        />
      </Card>
    </div>
  );
}

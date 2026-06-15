import { useEffect, useMemo, useState } from "react";
import { Button, Card, Col, Progress, Row, Statistic, Table, Tag, Tooltip } from "antd";
import { SyncOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { LinkUsage, SiteCapacity } from "../api/types";
import EChart from "../components/EChart";
import { linkUtilBarOption, utilColor } from "../charts/options";

function fmtBw(mbps: number) {
  return mbps >= 1000 ? `${Math.round(mbps / 1000)} Gbps` : `${mbps} Mbps`;
}

export default function Capacity() {
  const [sites, setSites] = useState<SiteCapacity[]>([]);
  const [links, setLinks] = useState<LinkUsage[]>([]);
  const [syncing, setSyncing] = useState(false);

  async function load() {
    const [s, l] = await Promise.all([
      api.get<SiteCapacity[]>("/capacity/sites"),
      api.get<LinkUsage[]>("/capacity/links/usage"),
    ]);
    setSites(s.data);
    setLinks(l.data);
  }

  async function syncBandwidth() {
    setSyncing(true);
    try {
      await api.post("/capacity/links/sync-bandwidth");
      await load();
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const totalCap = sites.reduce((a, s) => a + s.capacity_mbps, 0);
  const totalUsed = sites.reduce((a, s) => a + s.used_mbps, 0);

  const linkChart = useMemo(
    () => links.map((l) => ({ name: l.name, util: l.utilization_pct })),
    [links],
  );
  const linkOpt = useMemo(() => linkUtilBarOption(linkChart), [linkChart]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Row gutter={16}>
        <Col xs={24} md={6}>
          <Card className="chart-card">
            <Statistic title="Fabric 总容量" value={Math.round(totalCap / 1000)} suffix="Gbps" />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card className="chart-card">
            <Statistic
              title="已分配带宽"
              value={Math.round(totalUsed / 1000)}
              suffix="Gbps"
              valueStyle={{ color: "#1677ff" }}
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card className="chart-card">
            <div style={{ marginBottom: 8 }}>全域带宽分配率</div>
            <Progress
              percent={totalCap ? Math.round((totalUsed / totalCap) * 1000) / 10 : 0}
              strokeColor={utilColor(totalCap ? (totalUsed / totalCap) * 100 : 0)}
            />
          </Card>
        </Col>
      </Row>

      <Card className="chart-card" title="Fabric 站点容量">
        <Row gutter={16}>
          {sites.map((s) => (
            <Col xs={24} md={8} key={s.site_id}>
              <Card type="inner" title={`${s.code} · ${s.site}`}>
                <Progress
                  type="dashboard"
                  percent={s.utilization_pct}
                  strokeColor={utilColor(s.utilization_pct)}
                />
                <div>
                  {Math.round(s.used_mbps / 1000)} / {Math.round(s.capacity_mbps / 1000)} Gbps ·{" "}
                  {s.devices} 台设备
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      <Card
        className="chart-card"
        title="骨干链路 · 利用率"
        extra={
          <Tooltip title="从端口描述 bw(100Mbps) 同步链路合同带宽">
            <Button icon={<SyncOutlined />} loading={syncing} onClick={syncBandwidth}>
              同步端口带宽
            </Button>
          </Tooltip>
        }
      >
        <div style={{ color: "#666", fontSize: 12, marginBottom: 12 }}>
          端口描述标注 <Tag>bw(100Mbps)</Tag> 或 <Tag>bw(10Gbps)</Tag> · SNMP 发现后自动写入容量 · 利用率超 85% 触发告警
        </div>
        {linkChart.length ? (
          <EChart option={linkOpt} height={Math.max(240, linkChart.length * 36)} />
        ) : null}
        <Table
          rowKey="link_id"
          size="small"
          style={{ marginTop: 16 }}
          dataSource={links}
          pagination={false}
          columns={[
            { title: "链路", dataIndex: "name" },
            { title: "类型", dataIndex: "type", render: (t) => <Tag>{t}</Tag> },
            { title: "A 端", dataIndex: "device_a" },
            { title: "Z 端", dataIndex: "device_z" },
            {
              title: "合同带宽",
              dataIndex: "capacity_mbps",
              render: (v) => fmtBw(v),
            },
            {
              title: "实时流量",
              dataIndex: "traffic_mbps",
              render: (v) => (v != null ? fmtBw(v) : "-"),
            },
            {
              title: "峰值利用率",
              dataIndex: "utilization_pct",
              render: (v) => (
                <Progress percent={v} size="small" strokeColor={utilColor(v)} style={{ width: 120 }} />
              ),
            },
            {
              title: "已预留",
              dataIndex: "reserved_mbps",
              render: (v) => fmtBw(v),
            },
          ]}
        />
      </Card>
    </div>
  );
}

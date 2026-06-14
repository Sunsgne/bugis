import { useEffect, useState } from "react";
import { Card, Col, Progress, Row, Table, Tag, Statistic } from "antd";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { LinkUsage, SiteCapacity } from "../api/types";

function utilColor(p: number) {
  return p >= 85 ? "#cf1322" : p >= 60 ? "#fa8c16" : "#52c41a";
}

export default function Capacity() {
  const [sites, setSites] = useState<SiteCapacity[]>([]);
  const [links, setLinks] = useState<LinkUsage[]>([]);

  async function load() {
    const [s, l] = await Promise.all([
      api.get<SiteCapacity[]>("/capacity/sites"),
      api.get<LinkUsage[]>("/capacity/links/usage"),
    ]);
    setSites(s.data);
    setLinks(l.data);
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const totalCap = sites.reduce((a, s) => a + s.capacity_mbps, 0);
  const totalUsed = sites.reduce((a, s) => a + s.used_mbps, 0);

  const linkChart = links.map((l) => ({ name: l.name, util: l.utilization_pct }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Row gutter={16}>
        <Col xs={24} md={6}>
          <Card>
            <Statistic title="总容量" value={Math.round(totalCap / 1000)} suffix="Gbps" />
          </Card>
        </Col>
        <Col xs={24} md={6}>
          <Card>
            <Statistic
              title="已分配带宽"
              value={Math.round(totalUsed / 1000)}
              suffix="Gbps"
              valueStyle={{ color: "#1677ff" }}
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card>
            <div style={{ marginBottom: 8 }}>整体带宽分配率</div>
            <Progress
              percent={totalCap ? Math.round((totalUsed / totalCap) * 1000) / 10 : 0}
              strokeColor={utilColor(totalCap ? (totalUsed / totalCap) * 100 : 0)}
            />
          </Card>
        </Col>
      </Row>

      <Card title="数据中心容量">
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

      <Card title="链路利用率">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={linkChart}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis unit="%" domain={[0, 100]} />
            <Tooltip />
            <Bar dataKey="util" name="利用率(%)">
              {linkChart.map((d) => (
                <Cell key={d.name} fill={utilColor(d.util)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
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
              title: "容量",
              dataIndex: "capacity_mbps",
              render: (v) => `${Math.round(v / 1000)} Gbps`,
            },
            {
              title: "已预留",
              dataIndex: "reserved_mbps",
              render: (v) => `${Math.round(v / 1000)} Gbps`,
            },
            {
              title: "利用率",
              dataIndex: "utilization_pct",
              render: (v) => (
                <Progress percent={v} size="small" strokeColor={utilColor(v)} style={{ width: 120 }} />
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}

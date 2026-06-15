import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Progress,
  Row,
  Select,
  Statistic,
  Tag,
  App as AntApp,
  Empty,
} from "antd";
import { ReloadOutlined, ExperimentOutlined } from "@ant-design/icons";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
import { api } from "../api/client";
import type { Circuit, CircuitHealth, Paginated, TelemetrySample } from "../api/types";

export default function Monitoring() {
  const { message } = AntApp.useApp();
  const [circuits, setCircuits] = useState<Circuit[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [health, setHealth] = useState<CircuitHealth | null>(null);
  const [samples, setSamples] = useState<TelemetrySample[]>([]);
  const [billing, setBilling] = useState<any>(null);
  const [billMonth, setBillMonth] = useState<string | undefined>(undefined);

  async function loadBilling(id: number, period?: string) {
    const q = period ? `?period=${period}` : "";
    const { data } = await api.get(`/telemetry/circuits/${id}/billing${q}`);
    setBilling(data);
    setBillMonth(data.period);
  }

  async function loadCircuits() {
    const { data } = await api.get<Paginated<Circuit>>("/circuits?page=1&page_size=500&status=active");
    setCircuits(data.items);
    if (!selected && data.items.length) setSelected(data.items[0].id);
  }
  useEffect(() => {
    loadCircuits();
  }, []);

  async function loadData(id: number) {
    const [h, s] = await Promise.all([
      api.get<CircuitHealth>(`/telemetry/circuits/${id}/health`),
      api.get<TelemetrySample[]>(`/telemetry/circuits/${id}/samples?limit=60`),
    ]);
    setHealth(h.data);
    setSamples(s.data.slice().reverse());
  }
  useEffect(() => {
    if (selected) {
      loadData(selected);
      loadBilling(selected);
    }
  }, [selected]);

  useEffect(() => {
    if (!selected) return;
    const t = setInterval(() => loadData(selected), 7000);
    return () => clearInterval(t);
  }, [selected]);

  async function simulate() {
    const { data } = await api.post("/telemetry/simulate");
    message.success(`已为 ${data.generated} 条活跃专线生成采样`);
    if (selected) loadData(selected);
  }

  const chartData = samples.map((s, i) => ({
    idx: i + 1,
    rx: s.rx_mbps,
    tx: s.tx_mbps,
    util: s.utilization_pct,
    latency: s.latency_ms,
    loss: s.packet_loss_pct,
  }));

  const scoreColor = (v: number) => (v >= 90 ? "#52c41a" : v >= 70 ? "#fa8c16" : "#cf1322");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card>
        <Row align="middle" gutter={16}>
          <Col flex="auto">
            <Select
              style={{ width: 360 }}
              value={selected ?? undefined}
              onChange={setSelected}
              placeholder="选择专线"
              options={circuits.map((c) => ({
                value: c.id,
                label: `${c.code} · ${c.name}`,
              }))}
            />
          </Col>
          <Col>
            <Button icon={<ExperimentOutlined />} onClick={simulate} type="primary" ghost>
              生成模拟采样
            </Button>{" "}
            <Button
              icon={<ReloadOutlined />}
              onClick={() => selected && loadData(selected)}
            >
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      {health ? (
        <>
          <Row gutter={[16, 16]} align="stretch">
            <Col xs={24} md={6}>
              <Card
                style={{ height: "100%" }}
                styles={{
                  body: {
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                  },
                }}
              >
                <Progress
                  type="dashboard"
                  size={120}
                  percent={health.health_score}
                  strokeColor={scoreColor(health.health_score)}
                  format={(p) => `${p}`}
                />
                <div style={{ marginTop: 8, color: "#888" }}>健康评分</div>
              </Card>
            </Col>
            {[
              { t: "平均时延", v: health.avg_latency_ms, s: "ms" },
              { t: "抖动", v: health.avg_jitter_ms, s: "ms" },
              { t: "丢包率", v: health.avg_packet_loss_pct, s: "%",
                color: health.avg_packet_loss_pct > 0.2 ? "#cf1322" : undefined },
            ].map((m) => (
              <Col xs={12} md={4} key={m.t}>
                <Card
                  style={{ height: "100%" }}
                  styles={{ body: { display: "flex", alignItems: "center", height: "100%" } }}
                >
                  <Statistic title={m.t} value={m.v} suffix={m.s}
                    valueStyle={m.color ? { color: m.color } : undefined} />
                </Card>
              </Col>
            ))}
            <Col xs={24} md={6}>
              <Card
                style={{ height: "100%" }}
                styles={{ body: { display: "flex", flexDirection: "column", justifyContent: "center", height: "100%" } }}
              >
                <Statistic
                  title="峰值利用率"
                  value={health.peak_utilization_pct}
                  suffix={`% / ${health.bandwidth_mbps}Mbps`}
                />
                <div style={{ marginTop: 8 }}>
                  状态 <Tag color={health.status === "active" ? "green" : "default"}>{health.status}</Tag>
                  {health.sla_target && <Tag>SLA {health.sla_target}%</Tag>}
                </div>
              </Card>
            </Col>
          </Row>

          <Card
            title="月 95 计费 (95th percentile)"
            extra={
              <Select
                size="small"
                style={{ width: 140 }}
                value={billMonth}
                placeholder="选择月份"
                onChange={(m) => selected && loadBilling(selected, m)}
                options={(billing?.available_months || []).map((m: string) => ({ value: m, label: m }))}
              />
            }
          >
            {billing && billing.samples > 0 ? (
              <Row gutter={16}>
                <Col xs={12} md={6}>
                  <Statistic
                    title="计费带宽 (95)"
                    value={billing.billable_95_mbps}
                    suffix="Mbps"
                    valueStyle={{ color: "#1677ff", fontWeight: 700 }}
                  />
                </Col>
                <Col xs={12} md={5}>
                  <Statistic title="入向 95 (In)" value={billing.in_95_mbps} suffix="Mbps" />
                </Col>
                <Col xs={12} md={5}>
                  <Statistic title="出向 95 (Out)" value={billing.out_95_mbps} suffix="Mbps" />
                </Col>
                <Col xs={12} md={4}>
                  <Statistic title="峰值" value={billing.peak_mbps} suffix="Mbps" />
                </Col>
                <Col xs={12} md={4}>
                  <Statistic
                    title="计费利用率"
                    value={billing.utilization_pct}
                    suffix={`% / ${billing.bandwidth_mbps}M`}
                  />
                </Col>
                <Col span={24} style={{ marginTop: 8, color: "#888", fontSize: 12 }}>
                  统计周期 {billing.period} · 采样 {billing.samples} 点 · 取入/出向各自 95 百分位，按较高者计费（运营商惯例）
                </Col>
              </Row>
            ) : (
              <Empty description="本月暂无采样数据" />
            )}
          </Card>

          <Card title="流量 (Rx/Tx Mbps)">
            {chartData.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="idx" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Area type="monotone" dataKey="rx" stroke="#1677ff" fill="#1677ff33" name="Rx" />
                  <Area type="monotone" dataKey="tx" stroke="#52c41a" fill="#52c41a33" name="Tx" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <Empty description="暂无采样数据，点击“生成模拟采样”" />
            )}
          </Card>

          <Card title="时延 / 丢包">
            {chartData.length ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="idx" />
                  <YAxis yAxisId="left" />
                  <YAxis yAxisId="right" orientation="right" />
                  <Tooltip />
                  <Legend />
                  <Line yAxisId="left" type="monotone" dataKey="latency" stroke="#fa8c16" name="时延(ms)" dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="loss" stroke="#cf1322" name="丢包(%)" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <Empty />
            )}
          </Card>
        </>
      ) : (
        <Empty />
      )}
    </div>
  );
}

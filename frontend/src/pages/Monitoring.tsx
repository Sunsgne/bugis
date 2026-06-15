import { useEffect, useMemo, useState } from "react";
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
import { api } from "../api/client";
import type { Circuit, CircuitHealth, Paginated, TelemetrySample } from "../api/types";
import EChart from "../components/EChart";
import { latencyLossOption, trafficAreaOption } from "../charts/options";
import { action, empty } from "../constants/uiCopy";

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
    message.success(`已生成 ${data.generated} 条采样`);
    if (selected) loadData(selected);
  }

  const chartData = useMemo(
    () =>
      samples.map((s, i) => ({
        idx: i + 1,
        rx: s.rx_mbps,
        tx: s.tx_mbps,
        util: s.utilization_pct,
        latency: s.latency_ms,
        loss: s.packet_loss_pct,
      })),
    [samples],
  );

  const trafficOpt = useMemo(() => trafficAreaOption(chartData, "idx"), [chartData]);
  const slaOpt = useMemo(() => latencyLossOption(chartData), [chartData]);

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
              placeholder="选择 Circuit"
              options={circuits.map((c) => ({
                value: c.id,
                label: `${c.code} · ${c.name}`,
              }))}
            />
          </Col>
          <Col>
            <Button icon={<ExperimentOutlined />} onClick={simulate} type="primary" ghost>
              注入模拟流量
            </Button>{" "}
            <Button
              icon={<ReloadOutlined />}
              onClick={() => selected && loadData(selected)}
            >
              {action.refresh}
            </Button>
          </Col>
        </Row>
      </Card>

      {health ? (
        <>
          <Row gutter={[16, 16]} align="stretch">
            <Col xs={24} md={6}>
              <Card
                className="chart-card"
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
                <div style={{ marginTop: 8, color: "#888" }}>健康指数</div>
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
                  className="chart-card"
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
                className="chart-card"
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
            className="chart-card"
            title="95th 计费带宽"
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
              <Empty description={empty.traffic} />
            )}
          </Card>

          <Card className="chart-card" title="流量曲线 · Rx / Tx">
            {chartData.length ? (
              <EChart option={trafficOpt} height={280} />
            ) : (
              <Empty description={empty.traffic} />
            )}
          </Card>

          <Card className="chart-card" title="时延 · 丢包">
            {chartData.length ? (
              <EChart option={slaOpt} height={260} />
            ) : (
              <Empty description={empty.traffic} />
            )}
          </Card>
        </>
      ) : (
        <Empty description={empty.data} />
      )}
    </div>
  );
}

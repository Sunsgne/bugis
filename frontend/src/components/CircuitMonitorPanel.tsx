import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Card,
  Empty,
  Progress,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { api } from "../api/client";
import type {
  CircuitAvailability,
  CircuitHealth,
  TrafficSummary,
} from "../api/types";
import EChart from "./EChart";
import { latencyJitterOption, trafficWithP95Option } from "../charts/options";
import { empty } from "../constants/uiCopy";

const { Text } = Typography;

const HOUR_OPTIONS = [
  { value: 1, label: "近 1 小时" },
  { value: 6, label: "近 6 小时" },
  { value: 24, label: "近 24 小时" },
  { value: 168, label: "近 7 天" },
];

const EVENT_KIND: Record<string, { label: string; color: string }> = {
  interruption: { label: "中断", color: "red" },
  flash: { label: "闪断", color: "orange" },
};

type Props = {
  circuitId: number;
  compact?: boolean;
  pollSec?: number;
};

export default function CircuitMonitorPanel({ circuitId, compact = false, pollSec = 15 }: Props) {
  const [hours, setHours] = useState(compact ? 6 : 24);
  const [health, setHealth] = useState<CircuitHealth | null>(null);
  const [traffic, setTraffic] = useState<TrafficSummary | null>(null);
  const [availability, setAvailability] = useState<CircuitAvailability | null>(null);
  const [billing, setBilling] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!circuitId) return;
    setLoading(true);
    try {
      const limit = hours <= 6 ? 120 : hours <= 24 ? 288 : 500;
      const [h, t, a, b] = await Promise.all([
        api.get<CircuitHealth>(`/telemetry/circuits/${circuitId}/health`),
        api.get<TrafficSummary>(
          `/telemetry/circuits/${circuitId}/traffic-summary?hours=${hours}&limit=${limit}`,
        ),
        api.get<CircuitAvailability>(
          `/telemetry/circuits/${circuitId}/availability?hours=${hours}`,
        ),
        api.get(`/telemetry/circuits/${circuitId}/billing`),
      ]);
      setHealth(h.data);
      setTraffic(t.data);
      setAvailability(a.data);
      setBilling(b.data);
    } finally {
      setLoading(false);
    }
  }, [circuitId, hours]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!circuitId || pollSec <= 0) return;
    const t = setInterval(load, pollSec * 1000);
    return () => clearInterval(t);
  }, [circuitId, pollSec, load]);

  const chartData = useMemo(
    () =>
      (traffic?.samples || []).map((s) => ({
        t: s.created_at ? dayjs(s.created_at).format("HH:mm") : "",
        rx: s.rx_mbps,
        tx: s.tx_mbps,
        latency: s.latency_ms,
        jitter: s.jitter_ms,
        loss: s.packet_loss_pct,
      })),
    [traffic],
  );

  const trafficOpt = useMemo(
    () => trafficWithP95Option(chartData, "t", traffic?.p95),
    [chartData, traffic?.p95],
  );
  const latencyOpt = useMemo(() => latencyJitterOption(chartData, "t"), [chartData]);

  const scoreColor = (v: number) => (v >= 90 ? "#52c41a" : v >= 70 ? "#fa8c16" : "#cf1322");

  if (!health && loading) {
    return <Card loading />;
  }

  return (
    <div
      className={["circuit-monitor-panel", compact ? "circuit-monitor-panel--compact" : undefined]
        .filter(Boolean)
        .join(" ")}
      style={{ display: "flex", flexDirection: "column", gap: compact ? 12 : 16, flex: compact ? undefined : 1, minHeight: 0 }}
    >
      <Space wrap style={{ justifyContent: "space-between", width: "100%" }}>
        <Space wrap>
          <Text type="secondary">监控窗口</Text>
          <Select
            size="small"
            value={hours}
            style={{ width: 120 }}
            options={HOUR_OPTIONS}
            onChange={setHours}
          />
          {health?.tunnel_down && <Tag color="error">链路中断</Tag>}
        </Space>
        {!compact && billing?.billable_95_mbps != null && (
          <Text type="secondary">
            当月 95 计费带宽 <Text strong>{billing.billable_95_mbps} Mbps</Text>
          </Text>
        )}
      </Space>

      {health && (
        <div className={`monitor-kpi-row${compact ? " monitor-kpi-row--compact" : ""}`}>
          {!compact && (
            <Card size="small" className="chart-card">
              <div style={{ textAlign: "center" }}>
                <Progress
                  type="dashboard"
                  size={compact ? 80 : 100}
                  percent={health.health_score}
                  strokeColor={scoreColor(health.health_score)}
                  format={(p) => `${p}`}
                />
                <div style={{ color: "#888", fontSize: 12 }}>健康指数</div>
              </div>
            </Card>
          )}
          <Card size="small" className="chart-card">
            <Statistic title="平均时延" value={health.avg_latency_ms} suffix="ms" />
          </Card>
          <Card size="small" className="chart-card">
            <Statistic title="抖动" value={health.avg_jitter_ms} suffix="ms" />
          </Card>
          <Card size="small" className="chart-card">
            <Statistic
              title="可用率"
              value={availability?.uptime_pct ?? 100}
              suffix="%"
              valueStyle={{
                color: (availability?.uptime_pct ?? 100) < 99.9 ? "#cf1322" : "#52c41a",
              }}
            />
          </Card>
          <Card size="small" className="chart-card">
            <Statistic
              title="窗口 95 计费"
              value={traffic?.p95?.billable_95_mbps ?? 0}
              suffix="Mbps"
              valueStyle={{ color: "#1677ff" }}
            />
          </Card>
        </div>
      )}

      {availability && (availability.interruption_count > 0 || availability.flash_count > 0) && (
        <Alert
          type={availability.interruption_count > 0 ? "error" : "warning"}
          showIcon
          message={
            availability.interruption_count > 0
              ? `近 ${hours}h 发生 ${availability.interruption_count} 次中断，累计 ${Math.round(availability.total_downtime_sec / 60)} 分钟`
              : `近 ${hours}h 发生 ${availability.flash_count} 次闪断`
          }
          description={
            availability.flap_count >= 3
              ? `15 分钟内闪断 ${availability.flap_count} 次，请关注链路稳定性`
              : undefined
          }
        />
      )}

      <div className={compact ? undefined : "monitor-charts"}>
        <Card
          size="small"
          className="chart-card"
          title="流量 · Rx / Tx（含 95 参考线）"
          loading={loading}
        >
          {chartData.length ? (
            <EChart option={trafficOpt} height={compact ? 220 : "auto"} />
          ) : (
            <Empty description={empty.traffic} />
          )}
        </Card>

        <Card size="small" className="chart-card" title="时延 · 抖动 · 丢包" loading={loading}>
          {chartData.length ? (
            <EChart option={latencyOpt} height={compact ? 200 : "auto"} />
          ) : (
            <Empty description={empty.traffic} />
          )}
        </Card>
      </div>

      {availability && availability.events.length > 0 && (
        <Card size="small" title="中断 / 闪断事件">
          <Table
            size="small"
            rowKey="id"
            pagination={false}
            dataSource={availability.events}
            columns={[
              {
                title: "类型",
                dataIndex: "kind",
                width: 80,
                render: (k: string) => {
                  const m = EVENT_KIND[k] || { label: k, color: "default" };
                  return <Tag color={m.color}>{m.label}</Tag>;
                },
              },
              {
                title: "开始",
                dataIndex: "started_at",
                render: (v: string) => dayjs(v).format("MM-DD HH:mm:ss"),
              },
              {
                title: "结束",
                dataIndex: "ended_at",
                render: (v?: string) => (v ? dayjs(v).format("MM-DD HH:mm:ss") : "进行中"),
              },
              {
                title: "时长",
                dataIndex: "duration_sec",
                render: (v?: number) => (v != null ? `${v}s` : "-"),
              },
              { title: "来源", dataIndex: "source", width: 90 },
              { title: "说明", dataIndex: "detail", ellipsis: true },
            ]}
          />
        </Card>
      )}
    </div>
  );
}

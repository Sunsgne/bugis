import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Empty,
  Progress,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import { useUserDatetime } from "@/utils/datetime";
import type { Dayjs } from "dayjs";
import { api } from "../api/client";
import type {
  CircuitAvailability,
  CircuitHealth,
  TrafficBilling,
  TrafficSummary,
} from "../api/types";
import {
  buildRangeParams,
  chartRangeKey,
  HOUR_OPTIONS,
  sampleLimitForWindow,
  spanHoursFor,
  windowLabelFor,
  type RangeMode,
} from "../utils/monitorRange";
import EChart from "./EChart";
import { latencyJitterOption, trafficWithP95Option } from "../charts/options";
import { empty } from "../constants/uiCopy";
import { useTc } from "@/i18n/useTc";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const EVENT_KIND: Record<string, { label: string; color: string }> = {
  interruption: { label: "中断", color: "red" },
  flash: { label: "闪断", color: "orange" },
};

type Props = {
  circuitId: number;
  compact?: boolean;
  pollSec?: number;
  /** When false, hide latency/jitter/loss KPIs and charts. */
  latencyProbeEnabled?: boolean;
};

export default function CircuitMonitorPanel({
  circuitId,
  compact = false,
  pollSec = 15,
  latencyProbeEnabled = true,
}: Props) {
  const { tc } = useTc();
  const { timezone, timeLabel, formatFull, userNow } = useUserDatetime();
  const [rangeMode, setRangeMode] = useState<RangeMode>("preset");
  const [hours, setHours] = useState(compact ? 6 : 24);
  const [customRange, setCustomRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [health, setHealth] = useState<CircuitHealth | null>(null);
  const [traffic, setTraffic] = useState<TrafficSummary | null>(null);
  const [availability, setAvailability] = useState<CircuitAvailability | null>(null);
  const [billing, setBilling] = useState<TrafficBilling | null>(null);
  const [loading, setLoading] = useState(false);

  const spanHours = useMemo(
    () => spanHoursFor(rangeMode, hours, customRange),
    [rangeMode, customRange, hours],
  );

  const windowLabel = useMemo(
    () => windowLabelFor(rangeMode, hours, customRange, undefined, timezone),
    [rangeMode, customRange, hours, timezone],
  );

  const load = useCallback(async () => {
    if (!circuitId) return;
    if (rangeMode === "custom" && !customRange) return;
    setLoading(true);
    try {
      const rangeParams = buildRangeParams(rangeMode, hours, customRange, timezone);
      const limit = sampleLimitForWindow(rangeMode, hours, customRange);
      const [h, t, a, b] = await Promise.all([
        api.get<CircuitHealth>(`/telemetry/circuits/${circuitId}/health`, {
          params: { ...rangeParams, limit },
        }),
        api.get<TrafficSummary>(`/telemetry/circuits/${circuitId}/traffic-summary`, {
          params: { ...rangeParams, limit },
        }),
        api.get<CircuitAvailability>(`/telemetry/circuits/${circuitId}/availability`, {
          params: rangeParams,
        }),
        api.get<TrafficBilling>(`/telemetry/circuits/${circuitId}/billing`),
      ]);
      setHealth(h.data);
      setTraffic(t.data);
      setAvailability(a.data);
      setBilling(b.data);
    } finally {
      setLoading(false);
    }
  }, [circuitId, hours, rangeMode, customRange]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!circuitId || pollSec <= 0 || rangeMode === "custom") return;
    const t = setInterval(load, pollSec * 1000);
    return () => clearInterval(t);
  }, [circuitId, pollSec, load, rangeMode]);

  const chartData = useMemo(
    () =>
      (traffic?.samples || []).map((s) => ({
        t: timeLabel(s.created_at, spanHours),
        rx: s.rx_mbps,
        tx: s.tx_mbps,
      })),
    [traffic, spanHours, timeLabel],
  );

  const qosChartData = useMemo(
    () =>
      (traffic?.qos_samples || []).map((s) => ({
        t: timeLabel(s.created_at, spanHours),
        latency: s.latency_ms,
        jitter: s.jitter_ms,
        loss: s.packet_loss_pct,
      })),
    [traffic, spanHours, timeLabel],
  );

  const trafficOpt = useMemo(
    () => trafficWithP95Option(chartData, "t", traffic?.p95),
    [chartData, traffic?.p95],
  );
  const latencyOpt = useMemo(() => latencyJitterOption(qosChartData, "t"), [qosChartData]);
  const chartKey = chartRangeKey(circuitId, rangeMode, hours, customRange, chartData.length, timezone);
  const qosChartKey = chartRangeKey(circuitId, rangeMode, hours, customRange, qosChartData.length, timezone);

  const scoreColor = (v: number) => (v >= 90 ? "#52c41a" : v >= 70 ? "#fa8c16" : "#cf1322");
  const chartHeight = compact ? 220 : 280;

  if (!health && loading) {
    return <Card loading />;
  }

  return (
    <div
      className={["circuit-monitor-panel", compact ? "circuit-monitor-panel--compact" : undefined]
        .filter(Boolean)
        .join(" ")}
      style={{ display: "flex", flexDirection: "column", gap: compact ? 12 : 16 }}
    >
      <Space wrap style={{ justifyContent: "space-between", width: "100%" }}>
        <Space wrap>
          <Text type="secondary">{tc('时间范围')}</Text>
          <Select
            size="small"
            value={rangeMode}
            style={{ width: 88 }}
            options={[
              { value: "preset", label: "快捷" },
              { value: "custom", label: "自选" },
            ]}
            onChange={(v) => setRangeMode(v as RangeMode)}
          />
          {rangeMode === "preset" ? (
            <Select
              size="small"
              value={hours}
              style={{ width: 120 }}
              options={HOUR_OPTIONS}
              onChange={setHours}
            />
          ) : (
            <>
              <RangePicker
                size="small"
                showTime={{ format: "HH:mm" }}
                format="YYYY-MM-DD HH:mm"
                value={customRange}
                onChange={(vals) => setCustomRange(vals as [Dayjs, Dayjs] | null)}
                disabledDate={(current) => !!current && current > userNow().endOf("day")}
              />
              <Button size="small" type="primary" loading={loading} onClick={load}>{tc('查询')}</Button>
            </>
          )}
          {health?.tunnel_down && <Tag color="error">{tc('链路中断')}</Tag>}
          {latencyProbeEnabled && health && health.qos_samples === 0 && (
            <Tag color="default">{tc('QoS 待拨测')}</Tag>
          )}
          {!latencyProbeEnabled && <Tag color="default">{tc('延迟探测已关闭')}</Tag>}
        </Space>
        {!compact && billing?.billable_95_mbps != null && (
          <Text type="secondary">{tc('当月 95 计费带宽')}<Text strong>{billing.billable_95_mbps} Mbps</Text>
            <span style={{ marginLeft: 8, fontSize: 12 }}>({windowLabel})</span>
          </Text>
        )}
      </Space>

      {rangeMode === "custom" && !customRange && (
        <Alert type="info" showIcon message="请选择起始与终止时间后点击「查询」" />
      )}

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
                <div style={{ color: "#888", fontSize: 12 }}>{tc('健康指数')}</div>
              </div>
            </Card>
          )}
          {latencyProbeEnabled && (
            <>
              <Card size="small" className="chart-card">
                <Statistic title={tc('平均时延')} value={health.avg_latency_ms} suffix="ms" />
              </Card>
              <Card size="small" className="chart-card">
                <Statistic title={tc('抖动')} value={health.avg_jitter_ms} suffix="ms" />
              </Card>
            </>
          )}
          <Card size="small" className="chart-card">
            <Statistic
              title={tc('可用率')}
              value={availability?.uptime_pct ?? 100}
              suffix="%"
              valueStyle={{
                color: (availability?.uptime_pct ?? 100) < 99.9 ? "#cf1322" : "#52c41a",
              }}
            />
          </Card>
          <Card size="small" className="chart-card">
            <Statistic
              title={tc('窗口 95 计费')}
              value={traffic?.p95?.billable_95_mbps ?? 0}
              suffix="Mbps"
              valueStyle={{ color: "#ff6600" }}
            />
          </Card>
        </div>
      )}

      {availability && (availability.interruption_count > 0 || availability.flash_count > 0) && (
        <Alert
          className="circuit-monitor-flap-alert"
          type={availability.interruption_count > 0 ? "error" : "warning"}
          showIcon
          message={
            availability.interruption_count > 0
              ? `${windowLabel} 发生 ${availability.interruption_count} 次中断，累计 ${Math.round(availability.total_downtime_sec / 60)} 分钟`
              : `${windowLabel} 发生 ${availability.flash_count} 次闪断`
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
          title={`流量 · Rx / Tx（${windowLabel}，${chartData.length} 点）`}
          loading={loading}
        >
          {chartData.length ? (
            <EChart key={`traffic-${chartKey}`} option={trafficOpt} height={chartHeight} />
          ) : (
            <Empty description={empty.traffic} />
          )}
        </Card>

        {latencyProbeEnabled && (
          <Card
            size="small"
            className="chart-card"
            title={`时延 · 抖动 · 丢包（${windowLabel}）`}
            loading={loading}
          >
            {qosChartData.length ? (
              <EChart key={`latency-${qosChartKey}`} option={latencyOpt} height={chartHeight} />
            ) : (
              <Empty description={tc('暂无拨测数据 · 调度器轮询或手动「端到端拨测」后显示')} />
            )}
          </Card>
        )}
      </div>

      {availability && availability.events.length > 0 && (
        <Card size="small" title={tc('中断 / 闪断事件')}>
          <Table
            size="small"
            rowKey="id"
            pagination={false}
            dataSource={availability.events}
            columns={[
              {
                title: tc('类型'),
                dataIndex: "kind",
                width: 80,
                render: (k: string) => {
                  const m = EVENT_KIND[k] || { label: k, color: "default" };
                  return <Tag color={m.color}>{m.label}</Tag>;
                },
              },
              {
                title: tc('开始'),
                dataIndex: "started_at",
                render: (v: string) => formatFull(v),
              },
              {
                title: tc('结束'),
                dataIndex: "ended_at",
                render: (v?: string) => (v ? formatFull(v) : "进行中"),
              },
              {
                title: tc('时长'),
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

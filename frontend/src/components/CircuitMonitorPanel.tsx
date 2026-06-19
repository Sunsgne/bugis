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
import dayjs, { type Dayjs } from "dayjs";
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
  getHourOptions,
  sampleLimitForWindow,
  spanHoursFor,
  timeLabel,
  windowLabelFor,
  type RangeMode,
} from "../utils/monitorRange";
import EChart from "./EChart";
import { latencyJitterOption, trafficWithP95Option } from "../charts/options";
import { empty } from "../constants/uiCopy";
import { useTc } from "@/i18n/useTc";
import { useTranslation } from "react-i18next";

const { Text } = Typography;
const { RangePicker } = DatePicker;

function eventKindMeta(tc: (s: string) => string, kind: string) {
  const map: Record<string, { label: string; color: string }> = {
    interruption: { label: tc("中断"), color: "red" },
    flash: { label: tc("闪断"), color: "orange" },
  };
  return map[kind] || { label: kind, color: "default" };
}

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
  const { t } = useTranslation();
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

  const hourOptions = useMemo(() => getHourOptions(t), [t]);

  const windowLabel = useMemo(
    () => windowLabelFor(rangeMode, hours, customRange, t),
    [rangeMode, customRange, hours, t],
  );

  const load = useCallback(async () => {
    if (!circuitId) return;
    if (rangeMode === "custom" && !customRange) return;
    setLoading(true);
    try {
      const rangeParams = buildRangeParams(rangeMode, hours, customRange);
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
    [traffic, spanHours],
  );

  const qosChartData = useMemo(
    () =>
      (traffic?.qos_samples || []).map((s) => ({
        t: timeLabel(s.created_at, spanHours),
        latency: s.latency_ms,
        jitter: s.jitter_ms,
        loss: s.packet_loss_pct,
      })),
    [traffic, spanHours],
  );

  const trafficOpt = useMemo(
    () => trafficWithP95Option(chartData, "t", traffic?.p95),
    [chartData, traffic?.p95],
  );
  const latencyOpt = useMemo(() => latencyJitterOption(qosChartData, "t"), [qosChartData]);
  const chartKey = chartRangeKey(circuitId, rangeMode, hours, customRange, chartData.length);
  const qosChartKey = chartRangeKey(circuitId, rangeMode, hours, customRange, qosChartData.length);

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
              { value: "preset", label: tc("快捷") },
              { value: "custom", label: tc("自选") },
            ]}
            onChange={(v) => setRangeMode(v as RangeMode)}
          />
          {rangeMode === "preset" ? (
            <Select
              size="small"
              value={hours}
              style={{ width: 120 }}
              options={hourOptions}
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
                disabledDate={(current) => !!current && current > dayjs().endOf("day")}
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
        <Alert type="info" showIcon message={tc("请选择起始与终止时间后点击「查询」")} />
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
              ? t("monitor.interruptionAlert", {
                  window: windowLabel,
                  count: availability.interruption_count,
                  minutes: Math.round(availability.total_downtime_sec / 60),
                })
              : t("monitor.flashAlert", { window: windowLabel, count: availability.flash_count })
          }
          description={
            availability.flap_count >= 3
              ? t("monitor.flapWarning", { count: availability.flap_count })
              : undefined
          }
        />
      )}

      <div className={compact ? undefined : "monitor-charts"}>
        <Card
          size="small"
          className="chart-card"
          title={t("monitor.trafficChart", { window: windowLabel, points: chartData.length })}
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
            title={t("monitor.latencyChart", { window: windowLabel })}
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
                  const m = eventKindMeta(tc, k);
                  return <Tag color={m.color}>{m.label}</Tag>;
                },
              },
              {
                title: tc('开始'),
                dataIndex: "started_at",
                render: (v: string) => dayjs(v).format("MM-DD HH:mm:ss"),
              },
              {
                title: tc('结束'),
                dataIndex: "ended_at",
                render: (v?: string) => (v ? dayjs(v).format("MM-DD HH:mm:ss") : tc("进行中")),
              },
              {
                title: tc('时长'),
                dataIndex: "duration_sec",
                render: (v?: number) => (v != null ? `${v}s` : "-"),
              },
              { title: tc("来源"), dataIndex: "source", width: 90 },
              { title: tc("说明"), dataIndex: "detail", ellipsis: true },
            ]}
          />
        </Card>
      )}
    </div>
  );
}

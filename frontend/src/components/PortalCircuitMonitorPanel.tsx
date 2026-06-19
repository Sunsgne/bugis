import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Empty,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { api } from "../api/client";
import type { CircuitAvailability, CircuitHealth, TrafficBilling, TrafficSummary } from "../api/types";
import {
  buildRangeParams,
  chartRangeKey,
  HOUR_OPTIONS,
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

const { Text } = Typography;
const { RangePicker } = DatePicker;

type Props = {
  circuitId: number;
  compact?: boolean;
  pollSec?: number;
  latencyProbeEnabled?: boolean;
};

export default function PortalCircuitMonitorPanel({
  circuitId,
  compact = false,
  pollSec = 30,
  latencyProbeEnabled = true,
}: Props) {
  const { tc, t } = useTc();
  const [rangeMode, setRangeMode] = useState<RangeMode>("preset");
  const [hours, setHours] = useState(compact ? 6 : 24);
  const [customRange, setCustomRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [billingMonth, setBillingMonth] = useState<string | undefined>();
  const [health, setHealth] = useState<CircuitHealth | null>(null);
  const [traffic, setTraffic] = useState<TrafficSummary | null>(null);
  const [availability, setAvailability] = useState<CircuitAvailability | null>(null);
  const [billing, setBilling] = useState<TrafficBilling | null>(null);
  const [loading, setLoading] = useState(false);

  const base = `/portal/circuits/${circuitId}`;
  const spanHours = useMemo(
    () => spanHoursFor(rangeMode, hours, customRange),
    [rangeMode, hours, customRange],
  );
  const windowLabel = useMemo(
    () => windowLabelFor(rangeMode, hours, customRange),
    [rangeMode, hours, customRange],
  );

  const loadMetrics = useCallback(async () => {
    if (!circuitId) return;
    if (rangeMode === "custom" && !customRange) return;
    setLoading(true);
    try {
      const rangeParams = buildRangeParams(rangeMode, hours, customRange);
      const limit = sampleLimitForWindow(rangeMode, hours, customRange);
      const [h, t, a] = await Promise.all([
        api.get<CircuitHealth>(`${base}/health`, { params: { ...rangeParams, limit } }),
        api.get<TrafficSummary>(`${base}/traffic-summary`, { params: { ...rangeParams, limit } }),
        api.get<CircuitAvailability>(`${base}/availability`, { params: rangeParams }),
      ]);
      setHealth(h.data);
      setTraffic(t.data);
      setAvailability(a.data);
    } finally {
      setLoading(false);
    }
  }, [circuitId, hours, rangeMode, customRange, base]);

  const loadBilling = useCallback(async () => {
    if (!circuitId) return;
    try {
      const { data } = await api.get<TrafficBilling>(`${base}/billing`, {
        params: billingMonth && rangeMode === "preset" ? { period: billingMonth } : {},
      });
      setBilling(data);
      if (!billingMonth && data.available_months?.length) {
        setBillingMonth(data.available_months[0]);
      }
    } catch {
      /* billing is optional for chart rendering */
    }
  }, [circuitId, billingMonth, rangeMode, base]);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  useEffect(() => {
    loadBilling();
  }, [loadBilling]);

  useEffect(() => {
    if (!circuitId || pollSec <= 0 || rangeMode === "custom") return;
    const t = setInterval(loadMetrics, pollSec * 1000);
    return () => clearInterval(t);
  }, [circuitId, pollSec, loadMetrics, rangeMode]);

  const chartData = useMemo(
    () =>
      (traffic?.samples || []).map((s) => ({
        t: timeLabel(s.created_at, spanHours),
        rx: s.rx_mbps,
        tx: s.tx_mbps,
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
  const latencyOpt = useMemo(() => latencyJitterOption(chartData, "t"), [chartData]);
  const chartKey = chartRangeKey(circuitId, rangeMode, hours, customRange, chartData.length);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
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
            <Select size="small" value={hours} style={{ width: 120 }} options={HOUR_OPTIONS} onChange={setHours} />
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
              <Button size="small" type="primary" loading={loading} onClick={loadMetrics}>{tc('查询')}</Button>
            </>
          )}
        </Space>
        {billing?.billable_95_mbps != null && (
          <Text type="secondary">{tc('95 计费带宽')}<Text strong>{billing.billable_95_mbps} Mbps</Text>
            <span style={{ marginLeft: 8, fontSize: 12 }}>({billing.period || windowLabel})</span>
          </Text>
        )}
      </Space>

      {rangeMode === "custom" && !customRange && (
        <Alert type="info" showIcon message="请选择起始与终止时间后点击「查询」" />
      )}

      {rangeMode === "preset" && billing?.available_months?.length ? (
        <Space wrap>
          <Text type="secondary">{tc('月95 账期')}</Text>
          <Select
            size="small"
            style={{ width: 120 }}
            value={billingMonth}
            options={billing.available_months.map((m) => ({ value: m, label: m }))}
            onChange={setBillingMonth}
          />
          <Button size="small" onClick={loadBilling}>{tc('重算')}</Button>
        </Space>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
        <Card size="small">
          <Statistic title={tc('健康指数')} value={health?.health_score ?? 0} suffix="/ 100" />
        </Card>
        {latencyProbeEnabled && (
          <Card size="small">
            <Statistic title={tc('平均时延')} value={health?.avg_latency_ms ?? 0} suffix="ms" />
          </Card>
        )}
        <Card size="small">
          <Statistic title={tc('可用率')} value={availability?.uptime_pct ?? 100} suffix="%" />
        </Card>
        <Card size="small">
          <Statistic
            title={tc('窗口 95 计费')}
            value={traffic?.p95?.billable_95_mbps ?? 0}
            suffix="Mbps"
            valueStyle={{ color: "#ff6600" }}
          />
        </Card>
      </div>

      <Card size="small" title={`流量 · Rx / Tx（${windowLabel}，${chartData.length} 点）`} loading={loading}>
        {chartData.length ? (
          <EChart key={`traffic-${chartKey}`} option={trafficOpt} height={compact ? 220 : 280} />
        ) : (
          <Empty description={empty.traffic} />
        )}
      </Card>

      {latencyProbeEnabled && (
        <Card size="small" title={t("monitor.latencyChart", { window: windowLabel })} loading={loading}>
          {chartData.length ? (
            <EChart key={`latency-${chartKey}`} option={latencyOpt} height={compact ? 180 : 220} />
          ) : (
            <Empty description={empty.traffic} />
          )}
        </Card>
      )}

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
                render: (k: string) => (
                  <Tag color={k === "interruption" ? "red" : "orange"}>
                    {k === "interruption" ? "中断" : "闪断"}
                  </Tag>
                ),
              },
              {
                title: tc('开始'),
                dataIndex: "started_at",
                render: (v: string) => dayjs(v).format("MM-DD HH:mm:ss"),
              },
              {
                title: tc('时长'),
                dataIndex: "duration_sec",
                render: (v?: number) => (v != null ? `${v}s` : "-"),
              },
            ]}
          />
        </Card>
      )}
    </div>
  );
}

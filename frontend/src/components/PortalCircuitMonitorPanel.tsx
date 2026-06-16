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
import EChart from "./EChart";
import { latencyJitterOption, trafficWithP95Option } from "../charts/options";
import { empty } from "../constants/uiCopy";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const HOUR_OPTIONS = [
  { value: 1, label: "近 1 小时" },
  { value: 6, label: "近 6 小时" },
  { value: 24, label: "近 24 小时" },
  { value: 168, label: "近 7 天" },
  { value: 720, label: "近 30 天" },
];

type RangeMode = "preset" | "custom";

type Props = {
  circuitId: number;
  compact?: boolean;
  pollSec?: number;
};

function buildTrafficParams(mode: RangeMode, hours: number, customRange: [Dayjs, Dayjs] | null) {
  if (mode === "custom" && customRange) {
    const [start, end] = customRange;
    return { start_at: start.toISOString(), end_at: end.toISOString() };
  }
  return { hours };
}

function timeLabel(iso: string | undefined, spanHours: number) {
  if (!iso) return "";
  const fmt = spanHours > 24 ? "MM-DD HH:mm" : "HH:mm";
  return dayjs(iso).format(fmt);
}

function spanHoursFor(mode: RangeMode, hours: number, customRange: [Dayjs, Dayjs] | null) {
  if (mode === "custom" && customRange) {
    return Math.max(1, Math.ceil(customRange[1].diff(customRange[0], "hour", true)));
  }
  return hours;
}

export default function PortalCircuitMonitorPanel({
  circuitId,
  compact = false,
  pollSec = 30,
}: Props) {
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

  const load = useCallback(async () => {
    if (!circuitId) return;
    if (rangeMode === "custom" && !customRange) return;
    setLoading(true);
    try {
      const trafficParams = buildTrafficParams(rangeMode, hours, customRange);
      const availParams = buildTrafficParams(rangeMode, hours, customRange);
      const [h, t, a, b] = await Promise.all([
        api.get<CircuitHealth>(`${base}/health`),
        api.get<TrafficSummary>(`${base}/traffic-summary`, { params: trafficParams }),
        api.get<CircuitAvailability>(`${base}/availability`, { params: availParams }),
        api.get<TrafficBilling>(`${base}/billing`, {
          params: billingMonth && rangeMode === "preset" ? { period: billingMonth } : {},
        }),
      ]);
      setHealth(h.data);
      setTraffic(t.data);
      setAvailability(a.data);
      setBilling(b.data);
      if (!billingMonth && b.data.available_months?.length) {
        setBillingMonth(b.data.available_months[0]);
      }
    } finally {
      setLoading(false);
    }
  }, [circuitId, hours, rangeMode, customRange, billingMonth, base]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!circuitId || pollSec <= 0 || rangeMode === "custom") return;
    const t = setInterval(load, pollSec * 1000);
    return () => clearInterval(t);
  }, [circuitId, pollSec, load, rangeMode]);

  const spanHours = spanHoursFor(rangeMode, hours, customRange);

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

  const windowLabel =
    rangeMode === "custom" && customRange
      ? `${customRange[0].format("MM-DD HH:mm")} ~ ${customRange[1].format("MM-DD HH:mm")}`
      : HOUR_OPTIONS.find((o) => o.value === hours)?.label || `近 ${hours}h`;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Space wrap style={{ justifyContent: "space-between", width: "100%" }}>
        <Space wrap>
          <Text type="secondary">时间范围</Text>
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
              <Button size="small" type="primary" loading={loading} onClick={load}>
                查询
              </Button>
            </>
          )}
        </Space>
        {billing?.billable_95_mbps != null && (
          <Text type="secondary">
            95 计费带宽 <Text strong>{billing.billable_95_mbps} Mbps</Text>
            <span style={{ marginLeft: 8, fontSize: 12 }}>({billing.period || windowLabel})</span>
          </Text>
        )}
      </Space>

      {rangeMode === "custom" && !customRange && (
        <Alert type="info" showIcon message="请选择起始与终止时间后点击「查询」" />
      )}

      {rangeMode === "preset" && billing?.available_months?.length ? (
        <Space wrap>
          <Text type="secondary">月95 账期</Text>
          <Select
            size="small"
            style={{ width: 120 }}
            value={billingMonth}
            options={billing.available_months.map((m) => ({ value: m, label: m }))}
            onChange={setBillingMonth}
          />
          <Button size="small" onClick={load}>
            重算
          </Button>
        </Space>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
        <Card size="small">
          <Statistic title="健康指数" value={health?.health_score ?? 0} suffix="/ 100" />
        </Card>
        <Card size="small">
          <Statistic title="平均时延" value={health?.avg_latency_ms ?? 0} suffix="ms" />
        </Card>
        <Card size="small">
          <Statistic title="可用率" value={availability?.uptime_pct ?? 100} suffix="%" />
        </Card>
        <Card size="small">
          <Statistic
            title="窗口 95 计费"
            value={traffic?.p95?.billable_95_mbps ?? 0}
            suffix="Mbps"
            valueStyle={{ color: "#1677ff" }}
          />
        </Card>
      </div>

      <Card size="small" title="流量 · Rx / Tx（含 95 参考线）" loading={loading}>
        {chartData.length ? (
          <EChart option={trafficOpt} height={compact ? 220 : 280} />
        ) : (
          <Empty description={empty.traffic} />
        )}
      </Card>

      <Card size="small" title="时延 · 抖动 · 丢包" loading={loading}>
        {chartData.length ? (
          <EChart option={latencyOpt} height={compact ? 180 : 220} />
        ) : (
          <Empty description={empty.traffic} />
        )}
      </Card>

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
                render: (k: string) => (
                  <Tag color={k === "interruption" ? "red" : "orange"}>
                    {k === "interruption" ? "中断" : "闪断"}
                  </Tag>
                ),
              },
              {
                title: "开始",
                dataIndex: "started_at",
                render: (v: string) => dayjs(v).format("MM-DD HH:mm:ss"),
              },
              {
                title: "时长",
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

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert,
  Button,
  Empty,
  Select,
  Space,
  Spin,
  Tag,
  App as AntApp,
} from "antd";
import { ExperimentOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Circuit } from "../api/types";
import CircuitMonitorPanel from "../components/CircuitMonitorPanel";
import PageCard from "../components/PageCard";
import { action, empty, page } from "../constants/uiCopy";
import { fetchAllPages } from "../utils/pagination";
import { useTc } from "@/i18n/useTc";

const STATUS_COLOR: Record<string, string> = {
  active: "green",
  degraded: "orange",
  provisioning: "processing",
  pending: "gold",
  draft: "default",
  suspended: "volcano",
  failed: "red",
  decommissioned: "default",
};

const MONITORABLE = new Set(["active", "degraded", "provisioning", "pending", "draft", "failed"]);

function circuitStatusLabel(tc: (s: string) => string, status: string) {
  const map: Record<string, string> = {
    active: tc("运行中"),
    degraded: tc("降级"),
    provisioning: tc("开通中"),
    pending: tc("待开通"),
    draft: tc("草稿"),
    suspended: tc("暂停"),
    failed: tc("失败"),
    decommissioned: tc("已拆除"),
  };
  return map[status] || status;
}

export default function Monitoring() {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [params, setParams] = useSearchParams();
  const [circuits, setCircuits] = useState<Circuit[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);

  async function loadCircuits() {
    setLoading(true);
    try {
      let items = await fetchAllPages<Circuit>("/circuits", { status: "active" });
      if (!items.length) {
        const all = await fetchAllPages<Circuit>("/circuits");
        items = all.filter((c) => MONITORABLE.has(c.status));
      }
      setCircuits(items);
      const fromUrl = Number(params.get("circuit"));
      if (fromUrl && items.some((c) => c.id === fromUrl)) {
        setSelected(fromUrl);
      } else if (items.length) {
        setSelected(items[0].id);
        if (!fromUrl) setParams({ circuit: String(items[0].id) }, { replace: true });
      } else {
        setSelected(null);
      }
    } catch {
      message.error(tc('专线列表加载失败'));
      setCircuits([]);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCircuits();
  }, []);

  const circuitParam = params.get("circuit");
  useEffect(() => {
    const fromUrl = Number(circuitParam);
    if (fromUrl && circuits.some((c) => c.id === fromUrl)) {
      setSelected(fromUrl);
    }
  }, [circuitParam, circuits]);

  function selectCircuit(id: number) {
    setSelected(id);
    setParams({ circuit: String(id) });
  }

  async function collectNow() {
    const { data } = await api.post("/telemetry/collect");
    const msg =
      data.collected > 0
        ? tc(
            `SNMP 采集 ${data.collected} 条${data.skipped ? `，${data.skipped} 条跳过` : ""}`,
          )
        : tc(data.message || "无 SNMP 数据（请检查 SNMP 与接口 ifIndex）");
    message.info(msg);
    setRefreshKey((k) => k + 1);
  }

  const current = circuits.find((c) => c.id === selected);
  const showInactiveHint = current && current.status !== "active";

  return (
    <div className="monitoring-page">
      <PageCard title={page.monitoring} className="monitoring-header-card">
        <Spin spinning={loading}>
          <div className="monitoring-toolbar">
            <div className="monitoring-toolbar-main">
              {circuits.length ? (
                <Select
                  style={{ width: "100%" }}
                  value={selected ?? undefined}
                  onChange={selectCircuit}
                  placeholder={tc('选择专线')}
                  showSearch
                  optionFilterProp="label"
                  popupClassName="app-select-dropdown"
                  options={circuits.map((c) => ({
                    value: c.id,
                    label: `${c.code} · ${c.name}`,
                    status: c.status,
                  }))}
                  optionRender={(option) => (
                    <Space size={8}>
                      <span>{option.label}</span>
                      <Tag
                        bordered={false}
                        color={STATUS_COLOR[String(option.data.status)] || "default"}
                        style={{ margin: 0 }}
                      >
                        {circuitStatusLabel(tc, String(option.data.status))}
                      </Tag>
                    </Space>
                  )}
                />
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message={tc("暂无可监控专线")}
                  description={
                    <>
                      {tc("当前没有已激活（active）的专线。请先在")}{" "}
                      <Link to="/circuits">{page.circuits}</Link>{" "}
                      {tc("创建并开通专线，或点击刷新重试。")}
                    </>
                  }
                />
              )}
            </div>
            <div className="monitoring-toolbar-actions">
              <Space wrap>
                <Button icon={<ExperimentOutlined />} onClick={collectNow} type="primary" ghost>{tc('SNMP 采集')}</Button>
                <Button icon={<ReloadOutlined />} onClick={() => loadCircuits()}>
                  {action.refresh}
                </Button>
              </Space>
            </div>
          </div>
        </Spin>
      </PageCard>

      {showInactiveHint && current && (
        <Alert
          type="warning"
          showIcon
          message={tc(`专线 ${current.code} 当前状态为「${circuitStatusLabel(tc, current.status)}」`)}
          description={tc('SNMP 流量与可用性数据在专线激活（active）后通过 SNMP 与拨测采集；草稿/失败状态仅展示历史数据。')}
        />
      )}

      {selected ? (
        <CircuitMonitorPanel
          key={`${selected}-${refreshKey}`}
          circuitId={selected}
          pollSec={15}
          latencyProbeEnabled={current?.latency_probe_enabled !== false}
        />
      ) : (
        !loading && (
          <PageCard className="monitoring-empty-card">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={circuits.length ? empty.data : empty.circuits}
            >
              {!circuits.length && (
                <Link to="/circuits">
                  <Button type="primary" icon={<PlusOutlined />}>{tc('前往专线管理')}</Button>
                </Link>
              )}
            </Empty>
          </PageCard>
        )
      )}
    </div>
  );
}

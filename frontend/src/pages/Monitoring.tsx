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

const STATUS_LABEL: Record<string, string> = {
  active: "运行中",
  degraded: "降级",
  provisioning: "开通中",
  pending: "待开通",
  draft: "草稿",
  suspended: "暂停",
  failed: "失败",
  decommissioned: "已拆除",
};

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

export default function Monitoring() {
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
      message.error("专线列表加载失败");
      setCircuits([]);
      setSelected(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCircuits();
  }, []);

  function selectCircuit(id: number) {
    setSelected(id);
    setParams({ circuit: String(id) });
  }

  async function simulate() {
    const { data } = await api.post("/telemetry/simulate");
    message.success(`已采集 ${data.generated} 条 SNMP/模拟采样`);
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
                  placeholder="选择专线"
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
                        {STATUS_LABEL[String(option.data.status)] || option.data.status}
                      </Tag>
                    </Space>
                  )}
                />
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message="暂无可监控专线"
                  description={
                    <>
                      当前没有已激活（active）的专线。请先在
                      <Link to="/circuits"> 专线编排 </Link>
                      创建并开通专线，或点击刷新重试。
                    </>
                  }
                />
              )}
            </div>
            <div className="monitoring-toolbar-actions">
              <Space wrap>
                <Button icon={<ExperimentOutlined />} onClick={simulate} type="primary" ghost>
                  立即采集
                </Button>
                <Button icon={<ReloadOutlined />} onClick={() => loadCircuits()}>
                  {action.refresh}
                </Button>
              </Space>
            </div>
          </div>
        </Spin>
      </PageCard>

      {showInactiveHint && (
        <Alert
          type="warning"
          showIcon
          message={`专线 ${current.code} 当前状态为「${STATUS_LABEL[current.status] || current.status}」`}
          description="SNMP 流量与可用性数据在专线激活（active）后最为完整；草稿/失败状态仍可查看历史或模拟采样。"
        />
      )}

      {selected ? (
        <CircuitMonitorPanel key={`${selected}-${refreshKey}`} circuitId={selected} pollSec={15} />
      ) : (
        !loading && (
          <PageCard className="monitoring-empty-card">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={circuits.length ? empty.data : empty.circuits}
            >
              {!circuits.length && (
                <Link to="/circuits">
                  <Button type="primary" icon={<PlusOutlined />}>
                    前往专线编排
                  </Button>
                </Link>
              )}
            </Empty>
          </PageCard>
        )
      )}
    </div>
  );
}

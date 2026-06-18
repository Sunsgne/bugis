import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert, Empty, Select, Spin } from "antd";
import { api } from "../api/client";
import PortalCircuitMonitorPanel from "../components/PortalCircuitMonitorPanel";
import PageCard from "../components/PageCard";
import { useTc } from "@/i18n/useTc";

interface Row {
  id: number;
  code: string;
  name: string;
  status: string;
  bandwidth_mbps: number;
  latency_probe_enabled?: boolean;
}

const MONITORABLE = new Set(["active", "degraded", "provisioning"]);

export default function PortalTraffic() {
  const { tc } = useTc();
  const [params, setParams] = useSearchParams();
  const [circuits, setCircuits] = useState<Row[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const { data } = await api.get<Row[]>("/portal/circuits");
        const items = data.filter((c) => MONITORABLE.has(c.status));
        setCircuits(items);
        const fromUrl = Number(params.get("circuit"));
        if (fromUrl && items.some((c) => c.id === fromUrl)) {
          setSelected(fromUrl);
        } else if (items.length) {
          setSelected(items[0].id);
          setParams({ circuit: String(items[0].id) }, { replace: true });
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function onSelect(id: number) {
    setSelected(id);
    setParams({ circuit: String(id) }, { replace: true });
  }

  if (loading) return <Spin style={{ display: "block", margin: "80px auto" }} />;

  const current = circuits.find((c) => c.id === selected);

  return (
    <PageCard title={tc('流量洞察')} description={tc('5 分钟粒度采样 · 95 计费 · 历史数据永久保留')}>
      {circuits.length === 0 ? (
        <Empty description={tc('暂无可监控的运行中专线')} />
      ) : (
        <>
          <div style={{ marginBottom: 16 }}>
            <span style={{ marginRight: 8, color: "#666" }}>{tc('选择专线')}</span>
            <Select
              style={{ minWidth: 320 }}
              value={selected ?? undefined}
              onChange={onSelect}
              options={circuits.map((c) => ({
                value: c.id,
                label: `${c.code} · ${c.name} (${c.bandwidth_mbps}M)`,
              }))}
            />
          </div>
          <Alert
            type="info"
            showIcon
            message="95 计费说明"
            description={tc('系统按采样点聚合流量，取所选时间窗口内第 95 百分位作为计费带宽（入向/出向取较大值）。切换快捷时间范围会自动刷新图表；自选时间需点击「查询」。')}
            style={{ marginBottom: 16 }}
          />
          {selected ? (
            <PortalCircuitMonitorPanel
              circuitId={selected}
              pollSec={30}
              latencyProbeEnabled={current?.latency_probe_enabled !== false}
            />
          ) : null}
        </>
      )}
    </PageCard>
  );
}

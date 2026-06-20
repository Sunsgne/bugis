import { useEffect, useState } from "react";
import { Alert, Space } from "antd";
import { api } from "../api/client";
import type { LinkUsage, Topology as Topo } from "../api/types";
import PageCard from "@/components/PageCard";
import PhysicalTopologyFlow from "@/components/PhysicalTopologyFlow";
import TopologyLayoutControls from "@/components/TopologyLayoutControls";
import { Badge } from "@/components/ui/badge";
import { empty, page } from "../constants/uiCopy";
import { useTc } from "@/i18n/useTc";
import { useTopologyLayout } from "@/hooks/useTopologyLayout";

export default function Topology() {
  const { tc } = useTc();
  const [topo, setTopo] = useState<Topo | null>(null);
  const [links, setLinks] = useState<LinkUsage[]>([]);
  const [error, setError] = useState(false);
  const layout = useTopologyLayout();

  async function load() {
    try {
      const [topoRes, linksRes] = await Promise.all([
        api.get<Topo>("/capacity/topology"),
        api.get<LinkUsage[]>("/capacity/links/usage"),
      ]);
      setTopo(topoRes.data);
      setLinks(linksRes.data);
      await layout.loadLayout();
      setError(false);
    } catch {
      setError(true);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  if (error && !topo) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">{tc("拓扑数据加载失败，将自动重试…")}</div>
    );
  }

  if (!topo) {
    return <div className="py-16 text-center text-sm text-muted-foreground">{empty.data}</div>;
  }

  if (!topo.nodes.length) {
    return <div className="py-16 text-center text-sm text-muted-foreground">{empty.devices}</div>;
  }

  const linkStats = {
    dci: topo.edges.filter((e) => e.type === "dci").length,
    fabric: topo.edges.filter((e) => e.type === "intra_dc").length,
  };

  return (
    <PageCard
      className="topology-page-card"
      title={page.topology}
      extra={
        <Space wrap size="middle">
          <Badge variant="destructive">DCI {linkStats.dci}</Badge>
          <Badge variant="info">Fabric {linkStats.fabric}</Badge>
          <span className="text-xs text-muted-foreground">{tc("滚轮缩放 · 拖拽平移 · 拖动设备可调整布局")}</span>
          <TopologyLayoutControls
            layoutDirty={layout.layoutDirty}
            saving={layout.saving}
            autoSave={layout.autoSave}
            onAutoSaveChange={layout.toggleAutoSave}
            onSave={() => layout.saveLayout()}
            onReset={() => layout.resetLayout()}
          />
        </Space>
      }
    >
      {topo.edges.length === 0 && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={tc("尚未配置站点间链路")}
          description={tc("设备节点按互联关系自动布局；在「容量规划」中添加 DCI / Fabric 链路后，将显示设备间连线与带宽利用率。")}
        />
      )}
      <div className="topology-page-body">
        <PhysicalTopologyFlow
          topo={topo}
          links={links}
          savedPositions={layout.draftPositions}
          autoSave={layout.autoSave}
          onPositionsChange={layout.handlePositionsChange}
        />
      </div>
    </PageCard>
  );
}

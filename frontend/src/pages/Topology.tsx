import { useEffect, useState } from "react";
import { Alert } from "antd";
import { api } from "../api/client";
import type { Topology as Topo } from "../api/types";
import PageCard from "@/components/PageCard";
import PhysicalTopologyFlow from "@/components/PhysicalTopologyFlow";
import { Badge } from "@/components/ui/badge";
import { empty, page } from "../constants/uiCopy";

export default function Topology() {
  const [topo, setTopo] = useState<Topo | null>(null);

  async function load() {
    const { data } = await api.get<Topo>("/capacity/topology");
    setTopo(data);
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

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
        <>
          <Badge variant="destructive">DCI {linkStats.dci}</Badge>
          <Badge variant="info">Fabric {linkStats.fabric}</Badge>
          <span className="text-xs text-muted-foreground">滚轮缩放 · 拖拽平移</span>
        </>
      }
    >
      {topo.edges.length === 0 && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="尚未配置站点间链路"
          description="当前按站点泳道展示纳管设备。在「容量规划」中添加 DCI / Fabric 链路后，拓扑图将自动绘制互联关系与带宽利用率。"
        />
      )}
      <div className="topology-page-body">
        <PhysicalTopologyFlow topo={topo} />
      </div>
    </PageCard>
  );
}

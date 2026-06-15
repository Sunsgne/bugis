import { useEffect, useState } from "react";
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
          <span className="text-xs text-muted-foreground">滚轮缩放 · 拖拽平移 · 悬停高亮邻居</span>
        </>
      }
    >
      <PhysicalTopologyFlow topo={topo} />
    </PageCard>
  );
}

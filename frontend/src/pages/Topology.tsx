import { useEffect, useMemo, useState } from "react";
import { Card, Empty, Space, Tag, Typography } from "antd";
import { api } from "../api/client";
import type { Topology as Topo } from "../api/types";
import TopologyGraph from "../components/TopologyGraph";
import { physicalTopologyOption, EDGE_LABEL } from "../charts/topologyGraph";
import { empty, page } from "../constants/uiCopy";

const { Text } = Typography;

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

  const chartOpt = useMemo(() => (topo?.nodes.length ? physicalTopologyOption(topo) : null), [topo]);

  if (!topo) return <Empty description={empty.data} />;
  if (!topo.nodes.length) return <Empty description={empty.devices} />;

  const linkStats = {
    dci: topo.edges.filter((e) => e.type === "dci").length,
    fabric: topo.edges.filter((e) => e.type === "intra_dc").length,
  };

  return (
    <Card
      className="topology-page-card"
      title={page.topology}
      extra={
        <Space wrap size={[8, 4]}>
          <Tag color="red">DCI {linkStats.dci}</Tag>
          <Tag color="blue">Fabric {linkStats.fabric}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            滚轮缩放 · 拖拽平移 · 悬停高亮邻居
          </Text>
        </Space>
      }
    >
      <div className="topology-legend">
        {Object.entries(EDGE_LABEL).map(([k, label]) => (
          <span key={k} className={`topology-legend__item topology-legend__item--${k}`}>
            {label}
          </span>
        ))}
      </div>
      {chartOpt ? <TopologyGraph option={chartOpt} height={580} /> : <Empty description={empty.data} />}
    </Card>
  );
}

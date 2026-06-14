import { useEffect, useMemo, useState } from "react";
import { Card, Tag, Empty, Space } from "antd";
import { api } from "../api/client";
import type { Topology as Topo } from "../api/types";

const VENDOR_COLOR: Record<string, string> = {
  h3c: "#1677ff",
  huawei: "#cf1322",
  juniper: "#52c41a",
  arista: "#fa8c16",
  cisco: "#722ed1",
  frr: "#13c2c2",
};
const EDGE_COLOR: Record<string, string> = {
  dci: "#cf1322",
  intra_dc: "#1677ff",
  access: "#52c41a",
  uplink: "#722ed1",
};

interface Pos {
  x: number;
  y: number;
}

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

  const layout = useMemo(() => {
    if (!topo) return null;
    const colW = 280;
    const rowH = 90;
    const marginX = 120;
    const marginY = 80;
    const siteOrder = topo.sites.map((s) => s.id);
    const noSite = -1;
    const columns: number[] = [...siteOrder, noSite];
    const pos: Record<number, Pos> = {};
    columns.forEach((siteId, ci) => {
      const members = topo.nodes.filter(
        (n) => (n.site_id ?? noSite) === siteId
      );
      members.forEach((n, ri) => {
        pos[n.id] = { x: marginX + ci * colW, y: marginY + ri * rowH };
      });
    });
    const height =
      marginY +
      Math.max(
        1,
        ...columns.map(
          (siteId) =>
            topo.nodes.filter((n) => (n.site_id ?? noSite) === siteId).length
        )
      ) *
        rowH +
      40;
    const width = marginX + columns.length * colW;
    return { pos, width, height, colW, marginX, marginY };
  }, [topo]);

  if (!topo || !layout) return <Empty />;
  if (!topo.nodes.length) return <Empty description="暂无设备" />;

  return (
    <Card
      title="网络拓扑"
      extra={
        <Space>
          <Tag color="#cf1322">DCI 互联</Tag>
          <Tag color="#1677ff">DC 内链路</Tag>
        </Space>
      }
    >
      <div style={{ overflow: "auto" }}>
        <svg width={layout.width} height={layout.height} style={{ minWidth: "100%" }}>
          {/* site column headers */}
          {topo.sites.map((s, ci) => (
            <text
              key={s.id}
              x={layout.marginX + ci * layout.colW}
              y={36}
              fontSize={15}
              fontWeight={700}
              fill="#1677ff"
            >
              {s.code} · {s.name}
            </text>
          ))}

          {/* edges */}
          {topo.edges.map((e) => {
            const a = layout.pos[e.source];
            const z = layout.pos[e.target];
            if (!a || !z) return null;
            const util = e.capacity_mbps
              ? (e.reserved_mbps / e.capacity_mbps) * 100
              : 0;
            return (
              <g key={e.id}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={z.x}
                  y2={z.y}
                  stroke={EDGE_COLOR[e.type] || "#999"}
                  strokeWidth={e.type === "dci" ? 3 : 1.5}
                  strokeDasharray={e.type === "dci" ? "6 3" : ""}
                  opacity={0.7}
                />
                <text
                  x={(a.x + z.x) / 2}
                  y={(a.y + z.y) / 2 - 4}
                  fontSize={11}
                  fill="#888"
                  textAnchor="middle"
                >
                  {Math.round(e.capacity_mbps / 1000)}G · {util.toFixed(0)}%
                </text>
              </g>
            );
          })}

          {/* nodes */}
          {topo.nodes.map((n) => {
            const p = layout.pos[n.id];
            if (!p) return null;
            const color = VENDOR_COLOR[n.vendor] || "#666";
            return (
              <g key={n.id}>
                <rect
                  x={p.x - 70}
                  y={p.y - 22}
                  width={140}
                  height={44}
                  rx={8}
                  fill="#fff"
                  stroke={color}
                  strokeWidth={2}
                />
                <circle
                  cx={p.x - 56}
                  cy={p.y}
                  r={6}
                  fill={n.status === "online" ? "#52c41a" : "#bfbfbf"}
                />
                <text x={p.x - 44} y={p.y - 3} fontSize={12} fontWeight={600}>
                  {n.name}
                </text>
                <text x={p.x - 44} y={p.y + 12} fontSize={10} fill="#888">
                  {n.vendor.toUpperCase()} · {n.role}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </Card>
  );
}

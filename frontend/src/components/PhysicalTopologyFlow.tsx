import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { labelForOption, DEVICE_ROLE_OPTIONS } from "@/constants/formOptions";
import { vendorColors } from "@/charts/theme";
import type { Topology } from "@/api/types";

const EDGE_STYLE: Record<string, { color: string; strokeDasharray?: string }> = {
  dci: { color: "#ef4444", strokeDasharray: "6 4" },
  intra_dc: { color: "#6366f1" },
  access: { color: "#10b981" },
  uplink: { color: "#8b5cf6" },
};

function fmtG(mbps: number): string {
  return mbps >= 1000 ? `${(mbps / 1000).toFixed(0)}G` : `${mbps}M`;
}

function DeviceNode({ data }: { data: { label: string; meta: string; border: string; online: boolean } }) {
  return (
    <div
      className="rounded-lg border-2 bg-white px-3 py-2 shadow-md"
      style={{ borderColor: data.border, minWidth: 128 }}
    >
      <div className="flex items-center gap-1.5">
        <span className={`h-2 w-2 rounded-full ${data.online ? "bg-emerald-500" : "bg-slate-300"}`} />
        <span className="text-xs font-bold text-slate-800">{data.label}</span>
      </div>
      <div className="mt-0.5 text-[10px] text-slate-500">{data.meta}</div>
    </div>
  );
}

const nodeTypes = { device: DeviceNode };

type Props = {
  topo: Topology;
  className?: string;
};

export default function PhysicalTopologyFlow({ topo, className }: Props) {
  const NO_SITE = -1;
  const siteColumns = [
    ...topo.sites.map((s) => ({ id: s.id, label: `${s.code} · ${s.name}` })),
    ...(topo.nodes.some((n) => !n.site_id) ? [{ id: NO_SITE, label: "未分配站点" }] : []),
  ];

  const { nodes, edges } = useMemo(() => {
    const colW = 280;
    const rowH = 100;
    const marginX = 80;
    const marginY = 60;

    const flowNodes: Node[] = siteColumns.map((s, col) => ({
      id: `site-${s.id}`,
      type: "default",
      position: { x: marginX + col * colW - 40, y: 16 },
      data: { label: s.label },
      draggable: false,
      selectable: false,
      style: {
        background: "rgba(99,102,241,0.08)",
        border: "1px solid rgba(99,102,241,0.2)",
        borderRadius: 8,
        padding: "6px 12px",
        fontSize: 11,
        fontWeight: 600,
        color: "#334155",
      },
    }));

    topo.nodes.forEach((n) => {
      const colIdx = siteColumns.findIndex((s) => s.id === (n.site_id ?? NO_SITE));
      const col = Math.max(colIdx, 0);
      const row = topo.nodes.filter((m) => (m.site_id ?? NO_SITE) === (n.site_id ?? NO_SITE)).indexOf(n);
      const vendorColor = vendorColors[n.vendor] || "#64748b";
      flowNodes.push({
        id: String(n.id),
        type: "device",
        position: { x: marginX + col * colW, y: marginY + row * rowH },
        data: {
          label: n.name,
          meta: `${n.vendor.toUpperCase()} · ${labelForOption(DEVICE_ROLE_OPTIONS, n.role)}`,
          border: vendorColor,
          online: n.status === "online",
        },
      });
    });

    const nodeIds = new Set(topo.nodes.map((n) => String(n.id)));
    const flowEdges: Edge[] = topo.edges
      .filter((e) => nodeIds.has(String(e.source)) && nodeIds.has(String(e.target)))
      .map((e, i) => {
        const style = EDGE_STYLE[e.type] || EDGE_STYLE.intra_dc;
        const util = e.utilization_pct ?? (e.capacity_mbps ? (e.reserved_mbps / e.capacity_mbps) * 100 : 0);
        return {
          id: `e-${i}`,
          source: String(e.source),
          target: String(e.target),
          label: `${fmtG(e.capacity_mbps)} · ${util.toFixed(0)}%`,
          labelStyle: { fontSize: 10, fill: util > 80 ? "#dc2626" : "#475569" },
          labelBgStyle: { fill: "rgba(255,255,255,0.9)" },
          labelBgPadding: [4, 6] as [number, number],
          labelBgBorderRadius: 4,
          animated: e.type === "dci",
          style: { stroke: style.color, strokeWidth: e.type === "dci" ? 2.5 : 2, strokeDasharray: style.strokeDasharray },
          markerEnd: { type: MarkerType.ArrowClosed, color: style.color },
        };
      });

    return { nodes: flowNodes, edges: flowEdges };
  }, [topo, siteColumns]);

  return (
    <div className={className} style={{ width: "100%", height: 580 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.35}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} color="#e2e8f0" />
        <Controls showInteractive={false} />
        <MiniMap nodeStrokeWidth={2} zoomable pannable className="!bg-white/90" />
      </ReactFlow>
      <div className="mt-3 flex flex-wrap gap-2">
        {Object.entries(EDGE_STYLE).map(([k, v]) => (
          <Badge key={k} variant="outline" className="gap-2 font-normal">
            <span className="inline-block h-0.5 w-5 rounded" style={{ background: v.color }} />
            {k === "dci" ? "DCI 互联" : k === "intra_dc" ? "Fabric 内链路" : k}
          </Badge>
        ))}
      </div>
    </div>
  );
}

import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  MarkerType,
  MiniMap,
  ReactFlow,
  getBezierPath,
  useReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { labelForOption, DEVICE_ROLE_OPTIONS } from "@/constants/formOptions";
import { vendorColors } from "@/charts/theme";
import type { Topology } from "@/api/types";
import { useTc } from "@/i18n/useTc";
import { backboneUtilColor, fmtLinkBw } from "@/utils/linkUtilization";
import { layoutDeviceGraph, siteLabelForNode } from "@/utils/deviceGraphLayout";

const EDGE_STYLE: Record<string, { dash?: string; weight: number }> = {
  dci: { dash: "6 4", weight: 3 },
  intra_dc: { weight: 2.5 },
  access: { weight: 1.5 },
  uplink: { weight: 2 },
};

type EdgeData = {
  utilization_pct: number;
  shortLabel: string;
  title: string;
  linkType: string;
};

function fmtG(mbps: number): string {
  return mbps >= 1000 ? `${(mbps / 1000).toFixed(0)}G` : `${mbps}M`;
}

function shortHost(name: string, max = 28): string {
  if (name.length <= max) return name;
  const head = Math.ceil((max - 1) / 2);
  const tail = max - head - 1;
  return `${name.slice(0, head)}…${name.slice(-tail)}`;
}

function DeviceNode({
  data,
}: {
  data: {
    label: string;
    fullName: string;
    meta: string;
    siteLabel?: string | null;
    border: string;
    online: boolean;
    dimmed?: boolean;
  };
}) {
  return (
    <div
      className="device-graph-node rounded-xl border-2 bg-white px-3 py-2.5 shadow-sm transition-all hover:shadow-md"
      style={{
        borderColor: data.border,
        width: 220,
        opacity: data.dimmed ? 0.35 : 1,
      }}
      title={data.fullName}
    >
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${data.online ? "bg-emerald-500" : "bg-slate-300"}`} />
        <span className="truncate text-sm font-semibold text-slate-800">{data.label}</span>
        {data.siteLabel && (
          <span className="ml-auto shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
            {data.siteLabel}
          </span>
        )}
      </div>
      <div className="mt-1 truncate text-[11px] text-slate-500">{data.meta}</div>
    </div>
  );
}

function UtilizationEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
  markerEnd,
}: EdgeProps) {
  const d = data as EdgeData | undefined;
  const pct = d?.utilization_pct ?? 0;
  const color = backboneUtilColor(pct);
  const style = EDGE_STYLE[d?.linkType || "intra_dc"] || EDGE_STYLE.intra_dc;
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: color,
          strokeWidth: selected ? style.weight + 1.5 : style.weight,
          strokeDasharray: style.dash,
        }}
      />
      {d?.shortLabel && (
        <EdgeLabelRenderer>
          <div
            className="physical-topology-edge-label"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              borderColor: color,
            }}
            title={d.title}
          >
            {d.shortLabel}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = { device: DeviceNode };
const edgeTypes = { utilization: UtilizationEdge };

function FitViewOnLayout({ layoutKey }: { layoutKey: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const timer = window.setTimeout(() => {
      fitView({ padding: 0.12, maxZoom: 1.15, duration: 320 });
    }, 80);
    return () => window.clearTimeout(timer);
  }, [fitView, layoutKey]);
  return null;
}

function buildDeviceGraph(
  topo: Topology,
  size: { w: number; h: number },
  tc: (s: string) => string,
  highlightDeviceIds?: Set<number> | null,
): { nodes: Node[]; edges: Edge[] } {
  const positions = layoutDeviceGraph(
    topo.nodes.map((n) => ({ id: n.id, site_id: n.site_id })),
    topo.edges.map((e) => ({ source: e.source, target: e.target })),
    size.w,
    size.h,
  );

  const nodeById = new Map(topo.nodes.map((n) => [n.id, n]));
  const connected = new Set<number>();
  for (const e of topo.edges) {
    connected.add(e.source);
    connected.add(e.target);
  }
  const dimUnconnected = highlightDeviceIds != null && highlightDeviceIds.size > 0;

  const nodes: Node[] = topo.nodes.map((n) => {
    const pos = positions.get(n.id) ?? { x: 0, y: 0 };
    const siteLabel = siteLabelForNode(n.site_id, topo.sites);
    const vendorColor = vendorColors[n.vendor] || "#64748b";
    const dimmed = dimUnconnected
      ? !highlightDeviceIds!.has(n.id)
      : topo.edges.length > 0 && !connected.has(n.id);

    return {
      id: String(n.id),
      type: "device",
      position: pos,
      data: {
        label: shortHost(n.name),
        fullName: n.name,
        siteLabel,
        meta: `${n.vendor.toUpperCase()} · ${labelForOption(DEVICE_ROLE_OPTIONS, n.role)}`,
        border: vendorColor,
        online: n.status === "online",
        dimmed,
      },
    };
  });

  const nodeIds = new Set(topo.nodes.map((n) => String(n.id)));
  const edges: Edge[] = topo.edges
    .filter((e) => nodeIds.has(String(e.source)) && nodeIds.has(String(e.target)))
    .map((e, i) => {
      const util = e.utilization_pct ?? (e.capacity_mbps ? (e.reserved_mbps / e.capacity_mbps) * 100 : 0);
      const src = nodeById.get(e.source);
      const tgt = nodeById.get(e.target);
      const color = backboneUtilColor(util);
      const title = [
        src && tgt ? `${src.name} ↔ ${tgt.name}` : "",
        `${tc("峰值利用率")} ${util.toFixed(1)}%`,
        `${tc("合同带宽")} ${fmtLinkBw(e.capacity_mbps)}`,
        e.type === "dci" ? tc("DCI 互联") : tc("Fabric 内链路"),
      ]
        .filter(Boolean)
        .join("\n");

      return {
        id: `e-${e.id ?? i}`,
        source: String(e.source),
        target: String(e.target),
        type: "utilization",
        animated: e.type === "dci",
        data: {
          utilization_pct: util,
          shortLabel: `${fmtG(e.capacity_mbps)} · ${util.toFixed(0)}%`,
          title,
          linkType: e.type,
        } satisfies EdgeData,
        markerEnd: { type: MarkerType.ArrowClosed, color },
      };
    });

  return { nodes, edges };
}

type Props = {
  topo: Topology;
  className?: string;
};

export default function PhysicalTopologyFlow({ topo, className }: Props) {
  const { tc } = useTc();
  const hostRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 960, h: 560 });

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    const apply = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setSize({ w: rect.width, h: rect.height });
      }
    };
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { nodes, edges } = useMemo(
    () => buildDeviceGraph(topo, size, tc),
    [topo, size, tc],
  );
  const layoutKey = `${size.w}x${size.h}-${topo.nodes.length}-${topo.edges.length}`;

  return (
    <div ref={hostRef} className={["physical-topology-flow device-graph-flow", className].filter(Boolean).join(" ")}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        panOnDrag
        zoomOnScroll
        minZoom={0.35}
        maxZoom={1.6}
        proOptions={{ hideAttribution: true }}
      >
        <FitViewOnLayout layoutKey={layoutKey} />
        <Background gap={24} size={1} color="#e2e8f0" />
        <Controls showInteractive={false} position="bottom-right" />
        <MiniMap
          nodeStrokeWidth={2}
          zoomable
          pannable
          className="!rounded-lg !border !border-slate-200 !bg-white/95"
          position="bottom-left"
        />
      </ReactFlow>

      {topo.edges.length === 0 && (
        <div className="physical-topology-hint">
          {tc("暂无骨干链路 · 设备节点已按互联关系布局 · 在容量规划中添加链路后显示连线")}
        </div>
      )}

      <div className="physical-topology-legend">
        <span className="physical-topology-legend-item">
          <span className="physical-topology-legend-line" style={{ background: "#ef4444", opacity: 0.9 }} />
          {tc("DCI 互联")}
        </span>
        <span className="physical-topology-legend-item">
          <span className="physical-topology-legend-line" style={{ background: "#22c55e" }} />
          {tc("Fabric 内链路")} · &lt;50%
        </span>
        <span className="physical-topology-legend-item">
          <span className="physical-topology-legend-line" style={{ background: "#f59e0b" }} />
          50–84%
        </span>
        <span className="physical-topology-legend-item">
          <span className="physical-topology-legend-line" style={{ background: "#ef4444" }} />
          ≥85%
        </span>
      </div>
    </div>
  );
}

export { buildDeviceGraph };

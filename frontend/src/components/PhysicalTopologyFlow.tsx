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

const NO_SITE = -1;
const LANE_GUTTER = 12;
const LANE_HEADER = 52;

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
  data: { label: string; fullName: string; meta: string; border: string; online: boolean };
}) {
  return (
    <div
      className="rounded-xl border-2 bg-white px-3 py-2.5 shadow-sm transition-shadow hover:shadow-md"
      style={{ borderColor: data.border, width: 220 }}
      title={data.fullName}
    >
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${data.online ? "bg-emerald-500" : "bg-slate-300"}`} />
        <span className="truncate text-sm font-semibold text-slate-800">{data.label}</span>
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
          strokeWidth: selected ? style.weight + 1 : style.weight,
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
      fitView({ padding: 0.08, maxZoom: 1, duration: 280 });
    }, 60);
    return () => window.clearTimeout(timer);
  }, [fitView, layoutKey]);
  return null;
}

function buildSiteColumns(topo: Topology, unassignedLabel: string) {
  const columns = topo.sites
    .filter((s) => topo.nodes.some((n) => n.site_id === s.id))
    .map((s) => ({ id: s.id, label: `${s.code} · ${s.name}` }));
  if (topo.nodes.some((n) => !n.site_id)) {
    columns.push({ id: NO_SITE, label: unassignedLabel });
  }
  return columns;
}

function buildLayout(
  topo: Topology,
  size: { w: number; h: number },
  unassignedLabel: string,
  tc: (s: string) => string,
): { nodes: Node[]; edges: Edge[] } {
  const siteColumns = buildSiteColumns(topo, unassignedLabel);
  const laneCount = Math.max(siteColumns.length, 1);
  const canvasW = Math.max(size.w, 640);
  const canvasH = Math.max(size.h, 480);
  const laneW = (canvasW - LANE_GUTTER * (laneCount + 1)) / laneCount;
  const laneH = canvasH - LANE_GUTTER * 2;

  const nodes: Node[] = [];
  const nodeById = new Map(topo.nodes.map((n) => [n.id, n]));

  siteColumns.forEach((site, col) => {
    const laneId = `lane-${site.id}`;
    const laneX = LANE_GUTTER + col * (laneW + LANE_GUTTER);

    nodes.push({
      id: laneId,
      type: "group",
      position: { x: laneX, y: LANE_GUTTER },
      data: {},
      draggable: false,
      selectable: false,
      style: {
        width: laneW,
        height: laneH,
        backgroundColor: "rgba(255, 102, 0, 0.05)",
        border: "1px solid rgba(255, 102, 0, 0.16)",
        borderRadius: 14,
      },
    });

    nodes.push({
      id: `site-label-${site.id}`,
      parentId: laneId,
      type: "default",
      position: { x: 16, y: 12 },
      data: { label: site.label },
      draggable: false,
      selectable: false,
      style: {
        background: "transparent",
        border: "none",
        boxShadow: "none",
        fontSize: 12,
        fontWeight: 700,
        color: "#4f46e5",
        padding: 0,
        pointerEvents: "none",
      },
    });

    const devices = topo.nodes.filter((n) => (n.site_id ?? NO_SITE) === site.id);
    const nodeW = Math.min(220, laneW - 32);
    const nodeX = (laneW - nodeW) / 2;
    const usableH = laneH - LANE_HEADER - 24;
    const step = devices.length > 1 ? usableH / (devices.length - 1) : 0;
    const startY = devices.length === 1 ? LANE_HEADER + (usableH - 56) / 2 : LANE_HEADER;

    devices.forEach((n, row) => {
      const vendorColor = vendorColors[n.vendor] || "#64748b";
      nodes.push({
        id: String(n.id),
        type: "device",
        parentId: laneId,
        extent: "parent",
        position: { x: nodeX, y: devices.length === 1 ? startY : startY + row * step },
        data: {
          label: shortHost(n.name),
          fullName: n.name,
          meta: `${n.vendor.toUpperCase()} · ${labelForOption(DEVICE_ROLE_OPTIONS, n.role)}`,
          border: vendorColor,
          online: n.status === "online",
        },
      });
    });
  });

  const nodeIds = new Set(topo.nodes.map((n) => String(n.id)));
  const edges: Edge[] = topo.edges
    .filter((e) => nodeIds.has(String(e.source)) && nodeIds.has(String(e.target)))
    .map((e, i) => {
      const util = e.utilization_pct ?? (e.capacity_mbps ? (e.reserved_mbps / e.capacity_mbps) * 100 : 0);
      const src = nodeById.get(Number(e.source));
      const tgt = nodeById.get(Number(e.target));
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
        id: `e-${i}`,
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

  const unassignedLabel = tc("未分配站点");
  const { nodes, edges } = useMemo(
    () => buildLayout(topo, size, unassignedLabel, tc),
    [topo, size, unassignedLabel, tc],
  );
  const layoutKey = `${size.w}x${size.h}-${topo.nodes.length}-${topo.edges.length}`;

  return (
    <div ref={hostRef} className={["physical-topology-flow", className].filter(Boolean).join(" ")}>
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
        minZoom={0.5}
        maxZoom={1.4}
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
          {tc("暂无 DCI / Fabric 链路 · 设备按站点分列展示 · 在容量规划中添加链路后可显示互联关系")}
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

export { buildSiteColumns };

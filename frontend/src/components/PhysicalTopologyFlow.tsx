import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  MiniMap,
  ReactFlow,
  getBezierPath,
  useEdgesState,
  useNodesInitialized,
  useNodesState,
  useReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Tooltip } from "antd";
import { labelForOption, DEVICE_ROLE_OPTIONS } from "@/constants/formOptions";
import { vendorColors } from "@/charts/theme";
import type { LinkUsage, Topology } from "@/api/types";
import { useTc } from "@/i18n/useTc";
import { backboneUtilColor, fmtLinkBw } from "@/utils/linkUtilization";
import { layoutDeviceGraph, siteLabelForNode } from "@/utils/deviceGraphLayout";
import {
  curvatureForEdge,
  linkEdgeShortLabel,
  mergeTopologyEdges,
  utilizationMarker,
} from "@/utils/topologyEdges";
import LinkUtilizationTooltipContent from "./LinkUtilizationTooltipContent";
import LogicalPeerEdge from "./LogicalPeerEdge";
import DeviceGraphNode, {
  DEVICE_GRAPH_NODE_HEIGHT,
  DEVICE_GRAPH_NODE_WIDTH,
} from "./DeviceGraphNode";

const EDGE_STYLE: Record<string, { dash?: string; weight: number }> = {
  dci: { dash: "6 4", weight: 3 },
  intra_dc: { weight: 2.5 },
  access: { weight: 1.5 },
  uplink: { weight: 2 },
};

export type TopologyNodePositions = Record<string, { x: number; y: number }>;

type EdgeData = {
  link?: LinkUsage;
  utilization_pct: number;
  shortLabel: string;
  linkType: string;
  highlighted?: boolean;
  curvature?: number;
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

function UtilizationEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
  ...props
}: EdgeProps) {
  const { tc } = useTc();
  const d = data as EdgeData | undefined;
  const pct = d?.utilization_pct ?? 0;
  const color = backboneUtilColor(pct);
  const link = d?.link;
  const style = EDGE_STYLE[d?.linkType || "intra_dc"] || EDGE_STYLE.intra_dc;
  const [labelHover, setLabelHover] = useState(false);
  const showTooltip = Boolean(link && (labelHover || d?.highlighted));
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature: d?.curvature ?? 0.25,
  });

  return (
    <>
      <BaseEdge
        path={edgePath}
        {...props}
        interactionWidth={24}
        style={{
          ...props.style,
          stroke: color,
          strokeWidth: selected ? style.weight + 1.5 : style.weight,
          strokeDasharray: style.dash,
        }}
      />
      {d?.shortLabel && (
        <EdgeLabelRenderer>
          <Tooltip
            open={showTooltip}
            placement="top"
            mouseEnterDelay={0.12}
            overlayStyle={{ maxWidth: 420 }}
            title={link ? <LinkUtilizationTooltipContent link={link} pct={pct} tc={tc} /> : undefined}
          >
            <div
              className="physical-topology-edge-label backbone-edge-label nodrag nopan"
              style={{
                transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
                borderColor: color,
              }}
              onMouseEnter={() => setLabelHover(true)}
              onMouseLeave={() => setLabelHover(false)}
            >
              {d.shortLabel}
            </div>
          </Tooltip>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = { device: DeviceGraphNode };
const edgeTypes = { utilization: UtilizationEdge, logicalPeer: LogicalPeerEdge };

function FitViewOnLayout({ layoutKey }: { layoutKey: string }) {
  const { fitView } = useReactFlow();
  const nodesInitialized = useNodesInitialized({ includeHiddenNodes: false });
  useEffect(() => {
    if (!nodesInitialized) return;
    const timer = window.setTimeout(() => {
      fitView({ padding: 0.12, maxZoom: 1.15, duration: 320 });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [fitView, layoutKey, nodesInitialized]);
  return null;
}

function buildDeviceGraph(
  topo: Topology,
  size: { w: number; h: number },
  linksById: Map<number, LinkUsage>,
  savedPositions: TopologyNodePositions,
  tc: (zh: string) => string,
  highlightDeviceIds?: Set<number> | null,
  hoveredLinkId?: number | null,
): { nodes: Node[]; edges: Edge[] } {
  const autoPositions = layoutDeviceGraph(
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
    const saved = savedPositions[String(n.id)];
    const auto = autoPositions.get(n.id) ?? { x: 0, y: 0 };
    const pos = saved ?? auto;
    const siteLabel = siteLabelForNode(n.site_id, topo.sites);
    const vendorColor = vendorColors[n.vendor] || "#64748b";
    const dimmed = dimUnconnected
      ? !highlightDeviceIds!.has(n.id)
      : topo.edges.length > 0 && !connected.has(n.id);

    return {
      id: String(n.id),
      type: "device",
      position: pos,
      width: DEVICE_GRAPH_NODE_WIDTH,
      height: DEVICE_GRAPH_NODE_HEIGHT,
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
  const utilizationEdges: Edge[] = topo.edges
    .filter((e) => nodeIds.has(String(e.source)) && nodeIds.has(String(e.target)))
    .map((e, i) => {
      const link = linksById.get(e.id);
      const util = link?.utilization_pct ?? e.utilization_pct ?? (e.capacity_mbps ? (e.reserved_mbps / e.capacity_mbps) * 100 : 0);
      const highlighted = hoveredLinkId != null && link?.link_id === hoveredLinkId;

      return {
        id: `e-${e.id ?? i}`,
        source: String(e.source),
        target: String(e.target),
        type: "utilization",
        animated: e.type === "dci",
        interactionWidth: 24,
        data: {
          link,
          utilization_pct: util,
          shortLabel: link
            ? linkEdgeShortLabel(link, util)
            : `${fmtG(e.capacity_mbps)} · ${util.toFixed(0)}%`,
          linkType: e.type,
          highlighted,
          curvature: curvatureForEdge(topo.edges, e.id),
        } satisfies EdgeData,
        markerEnd: utilizationMarker(util),
      };
    });

  const links = [...linksById.values()];
  const edges = mergeTopologyEdges(utilizationEdges, links, nodeIds, tc);

  return { nodes, edges };
}

type Props = {
  topo: Topology;
  links: LinkUsage[];
  savedPositions: TopologyNodePositions;
  autoSave?: boolean;
  onPositionsChange?: (positions: TopologyNodePositions, options?: { autoSave?: boolean }) => void;
  className?: string;
};

export default function PhysicalTopologyFlow({
  topo,
  links,
  savedPositions,
  autoSave = false,
  onPositionsChange,
  className,
}: Props) {
  const { tc } = useTc();
  const hostRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 960, h: 560 });
  const [positions, setPositions] = useState<TopologyNodePositions>(savedPositions);
  const [hoveredLinkId, setHoveredLinkId] = useState<number | null>(null);

  useEffect(() => {
    setPositions(savedPositions);
  }, [savedPositions]);

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

  const linksById = useMemo(() => new Map(links.map((l) => [l.link_id, l])), [links]);

  const graphKey = `${size.w}x${size.h}-${topo.nodes.length}-${topo.edges.length}-${links.length}-${Object.keys(positions).length}`;

  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () => buildDeviceGraph(topo, size, linksById, positions, tc, null, hoveredLinkId),
    [topo, size, linksById, positions, tc, hoveredLinkId],
  );

  const onNodeDragStop = useCallback(
    (_: unknown, node: Node) => {
      setPositions((prev) => {
        const next = { ...prev, [node.id]: node.position };
        onPositionsChange?.(next, { autoSave });
        return next;
      });
    },
    [onPositionsChange, autoSave],
  );

  const [flowNodes, setFlowNodes, onNodesChange] = useNodesState<Node>(layoutNodes);
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState<Edge>(layoutEdges);

  useEffect(() => {
    setFlowNodes(layoutNodes);
  }, [layoutNodes, setFlowNodes]);

  useEffect(() => {
    setFlowEdges(layoutEdges);
  }, [layoutEdges, setFlowEdges]);

  return (
    <div ref={hostRef} className={["physical-topology-flow device-graph-flow", className].filter(Boolean).join(" ")}>
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        elevateEdgesOnSelect
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        onEdgeMouseEnter={(_, edge) => {
          const link = (edge.data as EdgeData | undefined)?.link;
          if (link) setHoveredLinkId(link.link_id);
        }}
        onEdgeMouseLeave={() => setHoveredLinkId(null)}
        panOnDrag
        zoomOnScroll
        minZoom={0.35}
        maxZoom={1.6}
        proOptions={{ hideAttribution: true }}
      >
        <FitViewOnLayout layoutKey={graphKey} />
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
        <span className="physical-topology-legend-item">
          <span
            className="physical-topology-legend-line"
            style={{ background: "transparent", borderTop: "2px dashed #64748b", width: 18, height: 0 }}
          />
          {tc("同链路对端")}
        </span>
      </div>
    </div>
  );
}

export { buildDeviceGraph };

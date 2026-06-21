import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesInitialized,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { labelForOption, DEVICE_ROLE_OPTIONS } from "@/constants/formOptions";
import { vendorColors } from "@/charts/theme";
import type { LinkUsage, Topology } from "@/api/types";
import { useTc } from "@/i18n/useTc";
import { layoutDeviceGraph, siteLabelForNode, edgeHandlePairForLayout, edgeHandlePairsForGraph, layoutEdgeCurvature, findHubNodeId, applySpokePeerSeparation } from "@/utils/deviceGraphLayout";
import {
  curvatureForEdge,
  linkEdgeShortLabel,
  mergeTopologyEdges,
} from "@/utils/topologyEdges";
import LogicalPeerEdge from "./LogicalPeerEdge";
import UtilizationEdge, { type UtilizationEdgeData } from "./UtilizationEdge";
import DeviceGraphNode, {
  DEVICE_GRAPH_NODE_HEIGHT,
  DEVICE_GRAPH_NODE_WIDTH,
} from "./DeviceGraphNode";

export type TopologyNodePositions = Record<string, { x: number; y: number }>;

type EdgeData = UtilizationEdgeData;

function fmtG(mbps: number): string {
  return mbps >= 1000 ? `${(mbps / 1000).toFixed(0)}G` : `${mbps}M`;
}

function shortHost(name: string, max = 28): string {
  if (name.length <= max) return name;
  const head = Math.ceil((max - 1) / 2);
  const tail = max - head - 1;
  return `${name.slice(0, head)}…${name.slice(-tail)}`;
}

const nodeTypes = { device: DeviceGraphNode };
const edgeTypes = { utilization: UtilizationEdge, logicalPeer: LogicalPeerEdge };

function FitViewOnLayout({ layoutKey }: { layoutKey: string }) {
  const { fitView } = useReactFlow();
  const nodesInitialized = useNodesInitialized({ includeHiddenNodes: false });
  useEffect(() => {
    if (!nodesInitialized) return;
    const timer = window.setTimeout(() => {
      fitView({ padding: 0.06, maxZoom: 1.35, duration: 280 });
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

  const connected = new Set<number>();
  for (const e of topo.edges) {
    connected.add(e.source);
    connected.add(e.target);
  }
  const dimUnconnected = highlightDeviceIds != null && highlightDeviceIds.size > 0;

  const posById = new Map<number, { x: number; y: number }>();
  for (const n of topo.nodes) {
    const saved = savedPositions[String(n.id)];
    posById.set(n.id, saved ?? autoPositions.get(n.id) ?? { x: 0, y: 0 });
  }

  const graphNodes = topo.nodes.map((n) => ({ id: n.id, site_id: n.site_id }));
  const graphEdges = topo.edges.map((e) => ({ source: e.source, target: e.target }));
  const hubId = findHubNodeId(graphNodes, graphEdges);
  const frozenLayoutIds = new Set(
    Object.keys(savedPositions)
      .map((id) => Number(id))
      .filter((id) => topo.nodes.some((n) => n.id === id)),
  );
  applySpokePeerSeparation(hubId, graphEdges, posById, undefined, frozenLayoutIds);

  const handlePairs = edgeHandlePairsForGraph(
    topo.edges.map((e) => ({ source: e.source, target: e.target, key: e.id })),
    posById,
  );

  const nodes: Node[] = topo.nodes.map((n) => {
    const pos = posById.get(n.id)!;
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
      const handles =
        handlePairs.get(String(e.id)) ??
        handlePairs.get(`${e.source}-${e.target}`) ??
        edgeHandlePairForLayout(e.source, e.target, posById);

      return {
        id: `e-${e.id ?? i}`,
        source: String(e.source),
        target: String(e.target),
        type: "utilization",
        animated: e.type === "dci",
        interactionWidth: 20,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        data: {
          link,
          utilization_pct: util,
          shortLabel: link
            ? linkEdgeShortLabel(link, util)
            : `${fmtG(e.capacity_mbps)} · ${util.toFixed(0)}%`,
          linkType: e.type,
          highlighted,
          curvature: layoutEdgeCurvature(
            e.source,
            e.target,
            posById,
            curvatureForEdge(topo.edges, e.id),
            handles,
          ),
        } satisfies EdgeData,
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

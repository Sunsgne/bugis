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
import { layoutDeviceGraph, layoutPathChain, siteLabelForNode, edgeHandlePairForLayout, edgeHandlePairsForGraph, layoutEdgeCurvature, findHubNodeId, applySpokePeerSeparation } from "@/utils/deviceGraphLayout";
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

function shortHost(name: string, max = 36): string {
  if (name.length <= max) return name;
  const head = Math.ceil((max - 1) / 2);
  const tail = max - head - 1;
  return `${name.slice(0, head)}…${name.slice(-tail)}`;
}

const nodeTypes = { device: DeviceGraphNode };
const edgeTypes = { utilization: UtilizationEdge, logicalPeer: LogicalPeerEdge };

function FitViewOnLayout({
  layoutKey,
  focusNodeIds,
}: {
  layoutKey: string;
  focusNodeIds?: string[];
}) {
  const { fitView } = useReactFlow();
  const nodesInitialized = useNodesInitialized({ includeHiddenNodes: false });
  useEffect(() => {
    if (!nodesInitialized) return;
    const timer = window.setTimeout(() => {
      if (focusNodeIds?.length) {
        fitView({
          nodes: focusNodeIds.map((id) => ({ id })),
          padding: 0.22,
          maxZoom: 1.15,
          duration: 320,
        });
        return;
      }
      fitView({ padding: 0.08, maxZoom: 1.25, duration: 280 });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [fitView, layoutKey, nodesInitialized, focusNodeIds]);
  return null;
}

function buildDeviceGraph(
  topo: Topology,
  size: { w: number; h: number },
  linksById: Map<number, LinkUsage>,
  savedPositions: TopologyNodePositions,
  tc: (zh: string) => string,
  highlightDeviceIds?: Set<number> | null,
  highlightLinkIds?: Set<number> | null,
  hoveredLinkId?: number | null,
  pathDeviceOrder?: number[] | null,
): { nodes: Node[]; edges: Edge[] } {
  const usePathChain =
    pathDeviceOrder != null
    && pathDeviceOrder.length >= 2
    && pathDeviceOrder.length <= 8
    && pathDeviceOrder.every((id) => topo.nodes.some((n) => n.id === id));

  const siteCount = new Set(topo.nodes.map((n) => n.site_id ?? -1)).size;
  const useSiteColumns = !usePathChain && siteCount >= 2 && topo.nodes.length >= 4;
  const pathFocus = !usePathChain
    && highlightLinkIds != null
    && highlightLinkIds.size > 0;

  const autoPositions = usePathChain
    ? layoutPathChain(pathDeviceOrder!, size.w, size.h)
    : layoutDeviceGraph(
      topo.nodes.map((n) => ({ id: n.id, site_id: n.site_id })),
      topo.edges.map((e) => ({ source: e.source, target: e.target })),
      size.w,
      size.h,
      topo.sites,
    );

  const connected = new Set<number>();
  for (const e of topo.edges) {
    connected.add(e.source);
    connected.add(e.target);
  }
  const dimUnconnected = !usePathChain && highlightDeviceIds != null && highlightDeviceIds.size > 0;

  const posById = new Map<number, { x: number; y: number }>();
  for (const n of topo.nodes) {
    const saved = savedPositions[String(n.id)];
    posById.set(n.id, saved ?? autoPositions.get(n.id) ?? { x: 0, y: 0 });
  }

  const graphEdges = topo.edges.map((e) => ({ source: e.source, target: e.target }));
  const frozenLayoutIds = new Set(
    Object.keys(savedPositions)
      .map((id) => Number(id))
      .filter((id) => topo.nodes.some((n) => n.id === id)),
  );
  if (!usePathChain && !useSiteColumns) {
    const hubId = findHubNodeId(
      topo.nodes.map((n) => ({ id: n.id, site_id: n.site_id })),
      graphEdges,
    );
    applySpokePeerSeparation(hubId, graphEdges, posById, undefined, frozenLayoutIds);
  }

  const handlePairs = edgeHandlePairsForGraph(
    topo.edges.map((e) => ({ source: e.source, target: e.target, key: e.id })),
    posById,
  );

  const nodes: Node[] = topo.nodes.map((n) => {
    const pos = posById.get(n.id)!;
    const siteLabel = siteLabelForNode(n.site_id, topo.sites);
    const vendorColor = vendorColors[n.vendor] || "#64748b";
    const dimmed = pathFocus && highlightDeviceIds
      ? !highlightDeviceIds.has(n.id)
      : dimUnconnected
        ? !highlightDeviceIds!.has(n.id)
        : topo.edges.length > 0 && !connected.has(n.id);
    const pathActive = Boolean(pathFocus && highlightDeviceIds?.has(n.id));

    return {
      id: String(n.id),
      type: "device",
      position: pos,
      width: DEVICE_GRAPH_NODE_WIDTH,
      height: DEVICE_GRAPH_NODE_HEIGHT,
      zIndex: pathActive ? 6 : dimmed ? 1 : 3,
      data: {
        label: shortHost(n.name),
        fullName: n.name,
        siteLabel,
        meta: `${n.vendor.toUpperCase()} · ${labelForOption(DEVICE_ROLE_OPTIONS, n.role)}`,
        border: vendorColor,
        online: n.status === "online",
        dimmed,
        pathActive,
      },
    };
  });

  const nodeIds = new Set(topo.nodes.map((n) => String(n.id)));
  const utilizationEdges: Edge[] = topo.edges
    .filter((e) => nodeIds.has(String(e.source)) && nodeIds.has(String(e.target)))
    .map((e, i) => {
      const link = linksById.get(e.id);
      const util = link?.utilization_pct ?? e.utilization_pct ?? (e.capacity_mbps ? (e.reserved_mbps / e.capacity_mbps) * 100 : 0);
      const pathHighlighted = highlightLinkIds != null && highlightLinkIds.size > 0 && highlightLinkIds.has(e.id);
      const highlighted = hoveredLinkId != null && link?.link_id === hoveredLinkId;
      const deemphasized = pathFocus && !pathHighlighted && !highlighted;
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
          pathHighlighted,
          deemphasized,
          curvature: layoutEdgeCurvature(
            e.source,
            e.target,
            posById,
            curvatureForEdge(topo.edges, e.id),
            handles,
          ),
        } satisfies EdgeData,
        zIndex: pathHighlighted ? 20 : deemphasized ? 0 : 2,
      };
    });

  const links = [...linksById.values()];
  const merged = mergeTopologyEdges(utilizationEdges, links, nodeIds, tc);
  const edges = merged.map((edge) => {
    if (edge.type === "logicalPeer" && pathFocus) {
      return {
        ...edge,
        style: { ...(edge.style as object), opacity: 0.1 },
        zIndex: 0,
      };
    }
    return edge;
  });

  return { nodes, edges };
}

type Props = {
  topo: Topology;
  links: LinkUsage[];
  savedPositions: TopologyNodePositions;
  autoSave?: boolean;
  onPositionsChange?: (positions: TopologyNodePositions, options?: { autoSave?: boolean }) => void;
  className?: string;
  highlightPath?: { deviceIds?: number[]; linkIds?: number[] };
  /** Fill parent height (mini embedded views) instead of default min-height viewport sizing. */
  fillContainer?: boolean;
  /** Ordered device ids for left-to-right path chain layout. */
  pathDeviceOrder?: number[];
};

export default function PhysicalTopologyFlow({
  topo,
  links,
  savedPositions,
  autoSave = false,
  onPositionsChange,
  className,
  highlightPath,
  fillContainer = false,
  pathDeviceOrder,
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
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) apply();
      },
      { threshold: 0.01 },
    );
    io.observe(el);
    return () => {
      ro.disconnect();
      io.disconnect();
    };
  }, []);

  const linksById = useMemo(() => new Map(links.map((l) => [l.link_id, l])), [links]);

  const highlightDeviceSet = useMemo(() => {
    const ids = highlightPath?.deviceIds;
    if (!ids?.length) return null;
    return new Set(ids);
  }, [highlightPath?.deviceIds]);

  const highlightLinkSet = useMemo(() => {
    const ids = highlightPath?.linkIds;
    if (!ids?.length) return null;
    return new Set(ids);
  }, [highlightPath?.linkIds]);

  const focusNodeIds = useMemo(() => {
    if (!highlightDeviceSet?.size) return undefined;
    return [...highlightDeviceSet].map(String);
  }, [highlightDeviceSet]);

  const graphKey = `${size.w}x${size.h}-${topo.nodes.length}-${topo.edges.length}-${links.length}-${Object.keys(positions).length}-${highlightPath?.deviceIds?.join(",") || ""}-${highlightPath?.linkIds?.join(",") || ""}-${pathDeviceOrder?.join(",") || ""}`;

  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () => buildDeviceGraph(
      topo,
      size,
      linksById,
      positions,
      tc,
      highlightDeviceSet,
      highlightLinkSet,
      hoveredLinkId,
      pathDeviceOrder,
    ),
    [topo, size, linksById, positions, tc, highlightDeviceSet, highlightLinkSet, hoveredLinkId, pathDeviceOrder],
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
    <div
      ref={hostRef}
        className={[
        "physical-topology-flow device-graph-flow",
        fillContainer ? "physical-topology-flow-fill" : "",
        highlightLinkSet?.size ? "physical-topology-flow-path-focus" : "",
        className,
      ].filter(Boolean).join(" ")}
    >
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
        <FitViewOnLayout layoutKey={graphKey} focusNodeIds={focusNodeIds} />
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
        {highlightLinkSet?.size ? (
          <span className="physical-topology-legend-item">
            <span className="physical-topology-legend-line" style={{ background: "#4f46e5", height: 3 }} />
            {tc("专线路径")}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export { buildDeviceGraph };

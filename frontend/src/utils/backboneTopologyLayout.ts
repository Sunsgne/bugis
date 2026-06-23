import type { Edge, Node } from "@xyflow/react";
import { labelForOption, DEVICE_ROLE_OPTIONS } from "@/constants/formOptions";
import { vendorColors } from "@/charts/theme";
import type { LinkUsage, Topology } from "@/api/types";
import { backboneUtilColor, fmtLinkBw } from "@/utils/linkUtilization";
import { layoutDeviceGraph, siteLabelForNode, edgeHandlePairForLayout, edgeHandlePairsForGraph, findHubNodeId, applySpokePeerSeparation } from "@/utils/deviceGraphLayout";
import {
  linkEdgeShortLabel,
  mergeTopologyEdges,
  stepOffsetForEdge,
} from "@/utils/topologyEdges";
import {
  DEVICE_GRAPH_NODE_HEIGHT,
  DEVICE_GRAPH_NODE_WIDTH,
} from "@/components/DeviceGraphNode";
import type { TopologyNodePositions } from "@/components/PhysicalTopologyFlow";

type EdgeData = {
  link?: LinkUsage;
  utilization_pct: number;
  shortLabel: string;
  highlighted?: boolean;
  pathMode?: "smoothstep";
  stepOffset?: number;
};

function shortHost(name: string, max = 26): string {
  if (name.length <= max) return name;
  const head = Math.ceil((max - 1) / 2);
  const tail = max - head - 1;
  return `${name.slice(0, head)}…${name.slice(-tail)}`;
}

export function buildFilteredTopo(topo: Topology, links: LinkUsage[]): Topology {
  if (!links.length) {
    return { ...topo, edges: [] };
  }
  const deviceIds = new Set<number>();
  for (const l of links) {
    deviceIds.add(l.device_a_id);
    deviceIds.add(l.device_z_id);
  }
  return {
    sites: topo.sites,
    nodes: topo.nodes.filter((n) => deviceIds.has(n.id)),
    edges: links.map((l) => ({
      id: l.link_id,
      name: l.name,
      type: l.type,
      source: l.device_a_id,
      target: l.device_z_id,
      capacity_mbps: l.capacity_mbps,
      reserved_mbps: l.reserved_mbps,
      utilization_pct: l.utilization_pct,
    })),
  };
}

export function buildBackboneTopologyLayout(
  topo: Topology,
  size: { w: number; h: number },
  linksById: Map<number, LinkUsage>,
  savedPositions: TopologyNodePositions,
  tc: (zh: string) => string,
  highlightLinkId?: number | null,
  highlightDeviceId?: number | null,
): { nodes: Node[]; edges: Edge[] } {
  const autoPositions = layoutDeviceGraph(
    topo.nodes.map((n) => ({ id: n.id, site_id: n.site_id })),
    topo.edges.map((e) => ({ source: e.source, target: e.target })),
    size.w,
    size.h,
  );

  const connectedDevices = new Set<number>();
  for (const e of topo.edges) {
    connectedDevices.add(e.source);
    connectedDevices.add(e.target);
  }
  if (highlightLinkId != null) {
    const link = linksById.get(highlightLinkId);
    if (link) {
      connectedDevices.add(link.device_a_id);
      connectedDevices.add(link.device_z_id);
    }
  }

  const highlightSet = new Set<number>();
  if (highlightDeviceId != null) {
    highlightSet.add(highlightDeviceId);
    for (const id of connectedDevices) highlightSet.add(id);
  } else if (highlightLinkId != null) {
    for (const id of connectedDevices) highlightSet.add(id);
  }

  const dimActive = highlightSet.size > 0;

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
    const vendorColor = vendorColors[n.vendor] || "#64748b";
    const dimmed = dimActive ? !highlightSet.has(n.id) : false;

    return {
      id: String(n.id),
      type: "device",
      position: pos,
      width: DEVICE_GRAPH_NODE_WIDTH,
      height: DEVICE_GRAPH_NODE_HEIGHT,
      data: {
        label: shortHost(n.name),
        fullName: n.name,
        siteLabel: siteLabelForNode(n.site_id, topo.sites),
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
      const link = linksById.get(e.id) ?? linksById.get(Number(e.id));
      const pct = link?.utilization_pct ?? e.utilization_pct ?? 0;
      const selected = highlightLinkId != null && link?.link_id === highlightLinkId;
      const color = backboneUtilColor(pct);
      const handles =
        handlePairs.get(String(e.id)) ??
        handlePairs.get(`${e.source}-${e.target}`) ??
        edgeHandlePairForLayout(e.source, e.target, posById);
      return {
        id: `e-${link?.link_id ?? i}`,
        source: String(e.source),
        target: String(e.target),
        type: "utilization",
        animated: pct >= 85,
        selected,
        interactionWidth: 24,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        data: {
          link,
          utilization_pct: pct,
          shortLabel: link ? linkEdgeShortLabel(link, pct) : `${fmtLinkBw(e.capacity_mbps)} · ${Math.round(pct)}%`,
          pathMode: "smoothstep",
          stepOffset: stepOffsetForEdge(topo.edges, e.id),
        } satisfies EdgeData,
        style: { stroke: color },
      };
    });

  const links = [...linksById.values()];
  const merged = mergeTopologyEdges(utilizationEdges, links, nodeIds, tc);
  const edges = merged.map((e) => {
    if (e.type !== "logicalPeer") return e;
    const srcId = Number(e.source);
    const tgtId = Number(e.target);
    const handles =
      handlePairs.get(`${srcId}-${tgtId}`) ??
      edgeHandlePairForLayout(srcId, tgtId, posById);
    return {
      ...e,
      sourceHandle: handles.sourceHandle,
      targetHandle: handles.targetHandle,
      data: {
        ...(e.data as object),
        pathMode: "smoothstep" as const,
      },
    };
  });

  return { nodes, edges };
}

export type { EdgeData as BackboneTopologyEdgeData };

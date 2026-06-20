import type { Edge } from "@xyflow/react";
import type { LinkUsage } from "@/api/types";
import { fmtLinkBw } from "@/utils/linkUtilization";
import { formatInterfaceShort } from "@/utils/networkDisplay";

export function devicePairKey(a: number, b: number): string {
  return `${Math.min(a, b)}-${Math.max(a, b)}`;
}

export function realLinkPairKeys(links: LinkUsage[]): Set<string> {
  const pairs = new Set<string>();
  for (const l of links) {
    pairs.add(devicePairKey(l.device_a_id, l.device_z_id));
  }
  return pairs;
}

export function linkVlanLabel(iface?: string | null): string | null {
  if (!iface) return null;
  const short = formatInterfaceShort(iface);
  if (short.startsWith("VLAN·")) return short;
  const dot = short.match(/·(\d+)$/);
  return dot ? `VLAN·${dot[1]}` : null;
}

/** Compact label on topology edges: supplier · VLAN · bandwidth · utilization. */
export function linkEdgeShortLabel(link: LinkUsage, pct: number): string {
  const vlan = linkVlanLabel(link.interface_a) || linkVlanLabel(link.interface_z);
  const supplier = link.supplier?.trim();
  const parts = [
    supplier,
    vlan,
    fmtLinkBw(link.capacity_mbps),
    `${Math.round(pct)}%`,
  ].filter(Boolean);
  return parts.join(" · ");
}

type TopoEdge = { id: number; source: number; target: number };

export function curvatureForEdge(edges: TopoEdge[], edgeId: number): number {
  const edge = edges.find((e) => e.id === edgeId);
  if (!edge) return 0.22;

  const samePair = edges.filter((e) => e.source === edge.source && e.target === edge.target);
  if (samePair.length > 1) {
    const idx = samePair.findIndex((e) => e.id === edgeId);
    const sign = idx % 2 === 0 ? 1 : -1;
    return sign * (0.22 + Math.floor(idx / 2) * 0.14);
  }

  const fromSource = edges.filter((e) => e.source === edge.source);
  if (fromSource.length > 1) {
    const idx = fromSource.findIndex((e) => e.id === edgeId);
    const sign = idx % 2 === 0 ? 1 : -1;
    return sign * (0.3 + Math.floor(idx / 2) * 0.12);
  }

  const toTarget = edges.filter((e) => e.target === edge.target);
  if (toTarget.length > 1) {
    const idx = toTarget.findIndex((e) => e.id === edgeId);
    const sign = idx % 2 === 0 ? 1 : -1;
    return sign * (0.26 + Math.floor(idx / 2) * 0.1);
  }

  return 0.18;
}

/** Dashed peer link between Z-end devices when multiple rows share the same link name. */
export function buildLogicalPeerEdges(
  links: LinkUsage[],
  nodeIds: Set<string>,
  tc: (zh: string) => string,
  realPairs: Set<string> = realLinkPairKeys(links),
): Edge[] {
  const byName = new Map<string, LinkUsage[]>();
  for (const l of links) {
    const key = l.name.trim();
    if (!key) continue;
    if (!byName.has(key)) byName.set(key, []);
    byName.get(key)!.push(l);
  }

  const edges: Edge[] = [];
  for (const [name, group] of byName) {
    if (group.length < 2) continue;
    const zIds = [...new Set(group.map((l) => l.device_z_id))];
    if (zIds.length < 2) continue;

    for (let i = 0; i < zIds.length; i += 1) {
      for (let j = i + 1; j < zIds.length; j += 1) {
        const aId = zIds[i];
        const bId = zIds[j];
        if (realPairs.has(devicePairKey(aId, bId))) continue;
        const a = String(aId);
        const b = String(bId);
        if (!nodeIds.has(a) || !nodeIds.has(b)) continue;
        const id = `logical-${Math.min(aId, bId)}-${Math.max(aId, bId)}-${name}`;
        edges.push({
          id,
          source: a,
          target: b,
          type: "logicalPeer",
          selectable: false,
          focusable: false,
          data: {
            label: `${name} · ${tc("对端互联")}`,
            curvature: -0.42,
          },
          style: { stroke: "#94a3b8", strokeWidth: 1.5, strokeDasharray: "8 5", opacity: 0.75 },
          zIndex: 0,
        });
      }
    }
  }
  return edges;
}

export function mergeTopologyEdges(
  utilizationEdges: Edge[],
  links: LinkUsage[],
  nodeIds: Set<string>,
  tc: (zh: string) => string,
): Edge[] {
  const realPairs = realLinkPairKeys(links);
  return [
    ...buildLogicalPeerEdges(links, nodeIds, tc, realPairs),
    ...utilizationEdges.map((e) => ({ ...e, zIndex: 1 })),
  ];
}

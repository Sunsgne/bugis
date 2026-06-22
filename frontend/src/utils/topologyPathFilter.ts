import type { LinkUsage, Topology } from "@/api/types";

/** Subset topology to devices/links on a computed forwarding path. */
export function filterTopologyForPath(
  topo: Topology,
  deviceIds: number[],
  linkIds: number[],
): Topology {
  if (!deviceIds.length) return topo;

  const deviceSet = new Set(deviceIds);
  const linkSet = new Set(linkIds);
  const siteIds = new Set<number>();

  const nodes = topo.nodes.filter((n) => {
    if (!deviceSet.has(n.id)) return false;
    if (n.site_id != null) siteIds.add(n.site_id);
    return true;
  });

  const edges = topo.edges.filter((e) => {
    if (linkSet.size > 0) return linkSet.has(e.id);
    return deviceSet.has(e.source) && deviceSet.has(e.target);
  });

  const sites = topo.sites.filter((s) => siteIds.has(s.id));

  return { sites, nodes, edges };
}

export function filterLinksForPath(links: LinkUsage[], linkIds: number[]): LinkUsage[] {
  if (!linkIds.length) return links;
  const linkSet = new Set(linkIds);
  return links.filter((l) => linkSet.has(l.link_id));
}

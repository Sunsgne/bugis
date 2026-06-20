/**
 * Sanity check: backbone topology layout must emit utilization + logical peer edges.
 * Run: npx tsx scripts/verify-topology-edges.ts
 */
import type { LinkUsage, Topology } from "../src/api/types";
import { buildBackboneTopologyLayout, buildFilteredTopo } from "../src/utils/backboneTopologyLayout";

const tc = (s: string) => s;

const topo: Topology = {
  sites: [
    { id: 1, code: "SHA2", name: "Shanghai" },
    { id: 2, code: "TYO2", name: "Tokyo 2" },
    { id: 3, code: "TYO3", name: "Tokyo 3" },
  ],
  nodes: [
    { id: 10, name: "cs-1.sha2", vendor: "huawei", role: "core", overlay_tech: "evpn", site_id: 1, status: "online" },
    { id: 20, name: "cs-1.tyo2", vendor: "huawei", role: "core", overlay_tech: "evpn", site_id: 2, status: "online" },
    { id: 30, name: "cs-2.tyo3", vendor: "huawei", role: "core", overlay_tech: "evpn", site_id: 3, status: "online" },
  ],
  edges: [],
};

const links: LinkUsage[] = [
  {
    link_id: 1,
    name: "SHA-TYO",
    type: "dci",
    supplier: "LANGQIAO",
    device_a_id: 10,
    device_z_id: 30,
    device_a: "cs-1.sha2",
    device_z: "cs-2.tyo3",
    site_a_id: 1,
    site_z_id: 3,
    site_a_code: "SHA2",
    site_z_code: "TYO3",
    capacity_mbps: 2000,
    reserved_mbps: 0,
    utilization_pct: 41,
  },
  {
    link_id: 2,
    name: "SHA-TYO",
    type: "dci",
    supplier: "ZENLAYER",
    device_a_id: 10,
    device_z_id: 20,
    device_a: "cs-1.sha2",
    device_z: "cs-1.tyo2",
    site_a_id: 1,
    site_z_id: 2,
    site_a_code: "SHA2",
    site_z_code: "TYO2",
    capacity_mbps: 600,
    reserved_mbps: 0,
    utilization_pct: 0,
  },
];

const filtered = buildFilteredTopo(topo, links);
const linksById = new Map(links.map((l) => [l.link_id, l]));
const { nodes, edges } = buildBackboneTopologyLayout(filtered, { w: 960, h: 1040 }, linksById, {}, tc);

const utilEdges = edges.filter((e) => e.type === "utilization");
const peerEdges = edges.filter((e) => e.type === "logicalPeer");

console.log(`nodes=${nodes.length} edges=${edges.length} util=${utilEdges.length} peer=${peerEdges.length}`);

if (nodes.length !== 3) {
  console.error("Expected 3 nodes");
  process.exit(1);
}
if (utilEdges.length !== 2) {
  console.error("Expected 2 utilization edges");
  process.exit(1);
}
if (peerEdges.length !== 1) {
  console.error("Expected 1 logical peer edge between TYO2 and TYO3");
  process.exit(1);
}

for (const e of utilEdges) {
  if (!e.source || !e.target) {
    console.error("Edge missing source/target", e);
    process.exit(1);
  }
}

const xs = nodes.map((n) => n.position.x);
const ys = nodes.map((n) => n.position.y);
const spreadX = Math.max(...xs) - Math.min(...xs);
const spreadY = Math.max(...ys) - Math.min(...ys);
console.log(`layout spread: ${Math.round(spreadX)}x${Math.round(spreadY)}`);

if (spreadX > 900 || spreadY > 900) {
  console.error("Layout too sparse — nodes spread too far apart");
  process.exit(1);
}
if (spreadX < 280) {
  console.error("Layout too tight — nodes overlapping");
  process.exit(1);
}

console.log("topology edge verification passed");

// Real TYO2↔TYO3 link replaces dashed logical peer edge
const linksWithDirect: LinkUsage[] = [
  ...links,
  {
    link_id: 3,
    name: "TYO-TYO",
    type: "dci",
    supplier: "ZENLAYER",
    device_a_id: 20,
    device_z_id: 30,
    device_a: "cs-1.tyo2",
    device_z: "cs-2.tyo3",
    site_a_id: 2,
    site_z_id: 3,
    site_a_code: "TYO2",
    site_z_code: "TYO3",
    capacity_mbps: 1000,
    reserved_mbps: 0,
    utilization_pct: 5,
  },
];

const filteredDirect = buildFilteredTopo(topo, linksWithDirect);
const layoutDirect = buildBackboneTopologyLayout(
  filteredDirect,
  { w: 960, h: 1040 },
  new Map(linksWithDirect.map((l) => [l.link_id, l])),
  {},
  tc,
);
const utilDirect = layoutDirect.edges.filter((e) => e.type === "utilization");
const peerDirect = layoutDirect.edges.filter((e) => e.type === "logicalPeer");

if (utilDirect.length !== 3) {
  console.error(`Expected 3 utilization edges with direct TYO2-TYO3 link, got ${utilDirect.length}`);
  process.exit(1);
}
if (peerDirect.length !== 0) {
  console.error("Logical peer edge should be omitted when a real link exists between TYO2 and TYO3");
  process.exit(1);
}

console.log("direct link replaces logical peer — passed");

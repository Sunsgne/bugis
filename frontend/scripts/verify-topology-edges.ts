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

console.log("topology edge verification passed");

/**
 * Sanity check: backbone topology layout must emit utilization + logical peer edges.
 * Run: npx tsx scripts/verify-topology-edges.ts
 */
import type { LinkUsage, Topology } from "../src/api/types";
import { buildBackboneTopologyLayout, buildFilteredTopo } from "../src/utils/backboneTopologyLayout";
import { edgeHandlePairsForGraph } from "../src/utils/deviceGraphLayout";

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
    device_a_id: 30,
    device_z_id: 20,
    device_a: "cs-2.tyo3",
    device_z: "cs-1.tyo2",
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

const tyo2 = layoutDirect.nodes.find((n) => n.id === "20");
const tyo3 = layoutDirect.nodes.find((n) => n.id === "30");
if (!tyo2 || !tyo3) {
  console.error("Missing TYO2/TYO3 nodes in layout");
  process.exit(1);
}
const peerSeparation = Math.abs(tyo2.position.x - tyo3.position.x);
if (peerSeparation < 80) {
  console.error(`TYO2-TYO3 nodes should be horizontally separated, got ${peerSeparation}px`);
  process.exit(1);
}
const peerEdge = utilDirect.find(
  (e) =>
    (e.source === "20" && e.target === "30") || (e.source === "30" && e.target === "20"),
);
if (!peerEdge) {
  console.error("Missing utilization edge between TYO2 and TYO3");
  process.exit(1);
}
const peerHandles = new Set([peerEdge.sourceHandle, peerEdge.targetHandle]);
const sideHandle = (h?: string) => h?.replace(/-(in|out)-\d+$/, "") ?? "";
const verticalPeer =
  sideHandle(peerEdge.sourceHandle) === "top" ||
  sideHandle(peerEdge.sourceHandle) === "bottom" ||
  sideHandle(peerEdge.targetHandle) === "top" ||
  sideHandle(peerEdge.targetHandle) === "bottom";
if (!verticalPeer) {
  console.error(
    `TYO2-TYO3 vertically stacked — expected top/bottom handles, got ${peerEdge.sourceHandle} → ${peerEdge.targetHandle}`,
  );
  process.exit(1);
}

console.log(`peer separation: ${Math.round(peerSeparation)}px`);
console.log(`peer handles: ${peerEdge.sourceHandle} → ${peerEdge.targetHandle}`);
console.log("direct link replaces logical peer — passed");

// Mesh hub: high-degree node should spread exits across multiple sides
const meshPairs = edgeHandlePairsForGraph(
  [
    { source: 10, target: 20, key: "a" },
    { source: 10, target: 30, key: "b" },
    { source: 10, target: 40, key: "c" },
  ],
  new Map([
    [10, { x: 100, y: 400 }],
    [20, { x: 500, y: 200 }],
    [30, { x: 520, y: 400 }],
    [40, { x: 480, y: 620 }],
  ]),
);
const meshSides = new Set(
  ["a", "b", "c"].map((k) => meshPairs.get(k)?.sourceSide).filter(Boolean),
);
if (meshSides.size < 2) {
  console.error(`Mesh hub should use multiple exit sides, got ${[...meshSides].join(",")}`);
  process.exit(1);
}
console.log(`mesh side spread: ${[...meshSides].join(", ")}`);
console.log("mesh handle spread — passed");

// Circuit path mini view: hub-and-spoke IGP path must stay left-to-right without overlap
import { layoutPathChain, applySpokePeerSeparation, findHubNodeId } from "../src/utils/deviceGraphLayout";

const pathOrder = [1, 2, 3];
const pathWidth = 720;
const pathHeight = 320;
const pathPositions = layoutPathChain(pathOrder, pathWidth, pathHeight);

// Spoke separation must NOT run on path chain — it collapses hub spokes onto the same column
const pathEdges = [
  { source: 1, target: 2 },
  { source: 3, target: 2 },
];
const hubId = findHubNodeId(
  pathOrder.map((id) => ({ id })),
  pathEdges,
);
const brokenPositions = new Map(pathPositions);
applySpokePeerSeparation(hubId, pathEdges, brokenPositions);
const brokenSep = Math.abs((brokenPositions.get(2)?.x ?? 0) - (brokenPositions.get(3)?.x ?? 0));
if (brokenSep >= 180) {
  console.error("Sanity check failed: spoke separation should collapse HKG3/FRA1 in star path");
  process.exit(1);
}

const pathSeparation = Math.abs((pathPositions.get(2)?.x ?? 0) - (pathPositions.get(3)?.x ?? 0));
if (pathSeparation < 180) {
  console.error(`Path chain nodes overlap — HKG3/FRA1 separation ${pathSeparation}px`);
  process.exit(1);
}

const chainXs = pathOrder.map((id) => pathPositions.get(id)?.x ?? 0);
if (chainXs[0] >= chainXs[1] || chainXs[1] >= chainXs[2]) {
  console.error(`Path chain X order broken: ${chainXs.join(", ")}`);
  process.exit(1);
}

console.log(`path chain separation HKG3-FRA1: ${Math.round(pathSeparation)}px`);
console.log("circuit path topology — passed");

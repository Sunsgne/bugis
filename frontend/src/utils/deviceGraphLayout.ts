/** Force-directed + compact hub layout for device topology graphs. */

export type LayoutGraphNode = { id: number; site_id?: number | null };
export type LayoutGraphEdge = { source: number; target: number };

const NODE_W = 220;
const NODE_H = 72;

type SimNode = { x: number; y: number; vx: number; vy: number; siteId: number };

function siteKey(siteId?: number | null): number {
  return siteId ?? -1;
}

/** Nodes that connect to each other without going through the hub. */
export function spokePeerNodeIds(hubId: number, edges: LayoutGraphEdge[]): Set<number> {
  const ids = new Set<number>();
  for (const e of edges) {
    if (e.source === e.target) continue;
    if (e.source !== hubId && e.target !== hubId) {
      ids.add(e.source);
      ids.add(e.target);
    }
  }
  return ids;
}

export function findHubNodeId(nodes: LayoutGraphNode[], edges: LayoutGraphEdge[]): number {
  const outDegree = new Map<number, number>();
  const degree = new Map<number, number>();
  for (const n of nodes) {
    outDegree.set(n.id, 0);
    degree.set(n.id, 0);
  }
  for (const e of edges) {
    if (e.source === e.target) continue;
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    outDegree.set(e.source, (outDegree.get(e.source) ?? 0) + 1);
  }
  let hubId = nodes[0]?.id ?? 0;
  let hubScore = -1;
  for (const n of nodes) {
    const score = (outDegree.get(n.id) ?? 0) * 10 + (degree.get(n.id) ?? 0);
    if (score > hubScore) {
      hubScore = score;
      hubId = n.id;
    }
  }
  return hubId;
}

/** Stagger spoke nodes with direct peer links so edges are not hidden under cards. */
export function applySpokePeerSeparation(
  hubId: number,
  edges: LayoutGraphEdge[],
  positions: Map<number, { x: number; y: number }>,
  anchorRightX?: number,
  frozenIds?: Set<number>,
): void {
  const peerIds = spokePeerNodeIds(hubId, edges);
  if (peerIds.size < 2) return;

  const adjustable = [...peerIds].filter((id) => !frozenIds?.has(id));
  if (adjustable.length < 2) return;

  const sorted = adjustable.sort((a, b) => {
    const ya = positions.get(a)?.y ?? 0;
    const yb = positions.get(b)?.y ?? 0;
    return ya - yb || a - b;
  });

  const baseX = anchorRightX ?? Math.max(...sorted.map((id) => positions.get(id)?.x ?? 0));
  const offset = Math.round(NODE_W * 0.58);

  sorted.forEach((id, idx) => {
    const pos = positions.get(id);
    if (!pos) return;
    positions.set(id, {
      x: baseX - (idx % 2) * offset,
      y: pos.y,
    });
  });
}

/** Left-to-right chain for a known forwarding path (mini circuit path view). */
export function layoutPathChain(
  deviceIds: number[],
  width: number,
  height: number,
): Map<number, { x: number; y: number }> {
  const map = new Map<number, { x: number; y: number }>();
  const n = deviceIds.length;
  if (n === 0) return map;

  const padX = Math.max(24, width * 0.04);
  const yCenter = height / 2 - NODE_H / 2;
  if (n === 1) {
    map.set(deviceIds[0], { x: width / 2 - NODE_W / 2, y: yCenter });
    return map;
  }

  const margin = 40;
  const minStep = NODE_W + margin;
  const innerWidth = Math.max(NODE_W, width - padX * 2);
  const packedStep = (innerWidth - NODE_W) / (n - 1);
  const step = Math.max(minStep, packedStep);
  const needsZigzag = packedStep < minStep;
  const startX = padX + Math.max(0, (innerWidth - NODE_W - step * (n - 1)) / 2);
  const yStagger = needsZigzag ? Math.min(NODE_H + 24, height * 0.22) : 0;

  deviceIds.forEach((id, i) => {
    const y =
      needsZigzag && yStagger > 0
        ? yCenter + (i % 2 === 0 ? -yStagger * 0.35 : yStagger * 0.65)
        : yCenter;
    map.set(id, { x: startX + step * i, y });
  });
  return map;
}

/** Ring layout for multipoint EVPN access PEs (equal spokes, no false A→Z chain). */
export function layoutMultipointRing(
  deviceIds: number[],
  width: number,
  height: number,
): Map<number, { x: number; y: number }> {
  const map = new Map<number, { x: number; y: number }>();
  const n = deviceIds.length;
  if (n === 0) return map;
  if (n === 1) {
    map.set(deviceIds[0], { x: width / 2 - NODE_W / 2, y: height / 2 - NODE_H / 2 });
    return map;
  }

  const pad = Math.max(48, Math.min(width, height) * 0.08);
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.max(
    NODE_W + pad,
    Math.min(width, height) / 2 - Math.max(NODE_W, NODE_H) / 2 - pad,
  );
  const angleStart = -Math.PI / 2;

  deviceIds.forEach((id, i) => {
    const angle = angleStart + (2 * Math.PI * i) / n;
    map.set(id, {
      x: cx - NODE_W / 2 + radius * Math.cos(angle),
      y: cy - NODE_H / 2 + radius * Math.sin(angle),
    });
  });
  return map;
}

/** Hub on the left, spokes stacked on the right — compact for small backbone graphs. */
function layoutCompactHub(
  nodes: LayoutGraphNode[],
  edges: LayoutGraphEdge[],
  width: number,
  height: number,
): Map<number, { x: number; y: number }> | null {
  if (nodes.length === 0) return null;

  if (nodes.length === 1) {
    return new Map([
      [nodes[0].id, { x: width / 2 - NODE_W / 2, y: height / 2 - NODE_H / 2 }],
    ]);
  }

  const degree = new Map<number, number>();
  const outDegree = new Map<number, number>();
  for (const n of nodes) {
    degree.set(n.id, 0);
    outDegree.set(n.id, 0);
  }
  for (const e of edges) {
    if (e.source === e.target) continue;
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    outDegree.set(e.source, (outDegree.get(e.source) ?? 0) + 1);
  }

  let hubId = nodes[0].id;
  let hubScore = -1;
  for (const n of nodes) {
    const score = (outDegree.get(n.id) ?? 0) * 10 + (degree.get(n.id) ?? 0);
    if (score > hubScore) {
      hubScore = score;
      hubId = n.id;
    }
  }

  const hubNeighbors = new Set<number>();
  for (const e of edges) {
    if (e.source === hubId) hubNeighbors.add(e.target);
    if (e.target === hubId) hubNeighbors.add(e.source);
  }

  const others = nodes.filter((n) => n.id !== hubId);
  if (hubNeighbors.size === 0 && edges.length > 0) return null;

  const padX = Math.max(32, width * 0.04);
  const padY = Math.max(40, height * 0.05);
  const leftX = padX;
  const rightX = width - padX - NODE_W;
  const spanX = rightX - leftX;
  if (spanX < NODE_W * 1.2) return null;

  const result = new Map<number, { x: number; y: number }>();
  result.set(hubId, { x: leftX, y: height / 2 - NODE_H / 2 });

  const spokes = others
    .filter((n) => hubNeighbors.has(n.id))
    .sort((a, b) => (a.site_id ?? 0) - (b.site_id ?? 0) || a.id - b.id);
  const detached = others
    .filter((n) => !hubNeighbors.has(n.id))
    .sort((a, b) => (a.site_id ?? 0) - (b.site_id ?? 0) || a.id - b.id);

  const rightNodes = [...spokes, ...detached];
  const count = rightNodes.length;
  const usableH = height - padY * 2 - NODE_H;
  const minGap = NODE_H * 1.35;
  const step = count <= 1 ? 0 : Math.max(minGap, Math.min(usableH / (count - 1), NODE_H * 2.4));
  const totalH = step * Math.max(count - 1, 0);
  const startY = height / 2 - totalH / 2;

  rightNodes.forEach((n, i) => {
    result.set(n.id, { x: rightX, y: startY + step * i });
  });

  applySpokePeerSeparation(hubId, edges, result, rightX);

  // Two-column fallback for many detached nodes
  if (detached.length > 2 && spokes.length > 0) {
    const midX = leftX + spanX * 0.58;
    spokes.forEach((n, i) => {
      const y = startY + step * i;
      result.set(n.id, { x: midX - NODE_W / 2, y });
    });
    const dStep = Math.max(minGap, Math.min(usableH / Math.max(detached.length - 1, 1), NODE_H * 2.2));
    const dTotal = dStep * Math.max(detached.length - 1, 0);
    const dStart = height / 2 - dTotal / 2;
    detached.forEach((n, i) => {
      result.set(n.id, { x: rightX, y: dStart + dStep * i });
    });
  }

  return result;
}

function initialPositions(
  nodes: LayoutGraphNode[],
  width: number,
  height: number,
): Map<number, SimNode> {
  const bySite = new Map<number, LayoutGraphNode[]>();
  for (const n of nodes) {
    const k = siteKey(n.site_id);
    if (!bySite.has(k)) bySite.set(k, []);
    bySite.get(k)!.push(n);
  }

  const siteIds = [...bySite.keys()];
  const cx = width / 2;
  const cy = height / 2;
  const orbitR = Math.min(width, height) * (nodes.length <= 4 ? 0.22 : 0.28);

  const siteCenters = new Map<number, { x: number; y: number }>();
  siteIds.forEach((sid, i) => {
    const angle = siteIds.length === 1 ? 0 : (2 * Math.PI * i) / siteIds.length - Math.PI / 2;
    siteCenters.set(sid, {
      x: cx + orbitR * Math.cos(angle),
      y: cy + orbitR * Math.sin(angle),
    });
  });

  const out = new Map<number, SimNode>();
  for (const [sid, members] of bySite) {
    const center = siteCenters.get(sid)!;
    const clusterR = Math.min(orbitR * 0.35, 32 + members.length * 22);
    members.forEach((n, idx) => {
      const angle =
        members.length === 1 ? 0 : (2 * Math.PI * idx) / members.length - Math.PI / 2;
      out.set(n.id, {
        x: center.x + clusterR * Math.cos(angle),
        y: center.y + clusterR * Math.sin(angle),
        vx: 0,
        vy: 0,
        siteId: sid,
      });
    });
  }
  return out;
}

function scalePositionsToFit(
  sim: Map<number, SimNode>,
  ids: number[],
  width: number,
  height: number,
): Map<number, { x: number; y: number }> {
  const pad = 28;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const id of ids) {
    const n = sim.get(id)!;
    minX = Math.min(minX, n.x);
    minY = Math.min(minY, n.y);
    maxX = Math.max(maxX, n.x);
    maxY = Math.max(maxY, n.y);
  }
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const targetFill = ids.length <= 4 ? 0.88 : 0.78;
  const scale = Math.min(
    ((width - pad * 2) / spanX) * targetFill,
    ((height - pad * 2) / spanY) * targetFill,
    ids.length <= 6 ? 2.8 : 1.6,
  );
  const offX = (width - spanX * scale) / 2 - minX * scale;
  const offY = (height - spanY * scale) / 2 - minY * scale;

  const result = new Map<number, { x: number; y: number }>();
  for (const id of ids) {
    const n = sim.get(id)!;
    result.set(id, {
      x: n.x * scale + offX - NODE_W / 2,
      y: n.y * scale + offY - NODE_H / 2,
    });
  }
  return result;
}

/**
 * Compute device positions for a network graph (devices ↔ links).
 * Returns top-left coordinates for each device node card (220×72).
 */
export function layoutDeviceGraph(
  nodes: LayoutGraphNode[],
  edges: LayoutGraphEdge[],
  width: number,
  height: number,
): Map<number, { x: number; y: number }> {
  if (!nodes.length) return new Map();

  if (nodes.length <= 12) {
    const hub = layoutCompactHub(nodes, edges, width, height);
    if (hub && hub.size === nodes.length) return hub;
  }

  const sim = initialPositions(nodes, width, height);
  const ids = nodes.map((n) => n.id);
  const cx = width / 2;
  const cy = height / 2;

  const linkPairs: { a: number; b: number }[] = [];
  for (const e of edges) {
    if (sim.has(e.source) && sim.has(e.target) && e.source !== e.target) {
      linkPairs.push({ a: e.source, b: e.target });
    }
  }

  const small = nodes.length <= 4;
  const iterations = linkPairs.length > 0 ? (small ? 100 : 140) : 40;
  const idealLen = Math.min(width, height) * (small ? 0.26 : 0.32);
  const repulsion = small ? 6400 : 8200;
  const spring = small ? 0.055 : 0.045;
  const damping = 0.84;

  for (let t = 0; t < iterations; t += 1) {
    const cooling = 1 - t / iterations;

    for (let i = 0; i < ids.length; i += 1) {
      for (let j = i + 1; j < ids.length; j += 1) {
        const na = sim.get(ids[i])!;
        const nb = sim.get(ids[j])!;
        let dx = na.x - nb.x;
        let dy = na.y - nb.y;
        let dist = Math.hypot(dx, dy) || 0.01;
        const force = (repulsion * cooling) / (dist * dist);
        dx = (dx / dist) * force;
        dy = (dy / dist) * force;
        na.vx += dx;
        na.vy += dy;
        nb.vx -= dx;
        nb.vy -= dy;
      }
    }

    for (const { a, b } of linkPairs) {
      const na = sim.get(a)!;
      const nb = sim.get(b)!;
      let dx = nb.x - na.x;
      let dy = nb.y - na.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const stretch = dist - idealLen;
      const force = spring * stretch * cooling;
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      na.vx += dx;
      na.vy += dy;
      nb.vx -= dx;
      nb.vy -= dy;
    }

    for (const id of ids) {
      const n = sim.get(id)!;
      n.vx += (cx - n.x) * 0.006 * cooling;
      n.vy += (cy - n.y) * 0.006 * cooling;
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
      n.x = Math.max(NODE_W / 2 + 16, Math.min(width - NODE_W / 2 - 16, n.x));
      n.y = Math.max(NODE_H / 2 + 16, Math.min(height - NODE_H / 2 - 16, n.y));
    }
  }

  return scalePositionsToFit(sim, ids, width, height);
}

export function siteLabelForNode(
  siteId: number | null | undefined,
  sites: { id: number; code: string; name: string }[],
): string | null {
  if (siteId == null) return null;
  const s = sites.find((x) => x.id === siteId);
  return s ? s.code : null;
}

export type EdgeHandleSide = "top" | "bottom" | "left" | "right";

/** Number of connection slots per side on each device node (reduces edge overlap). */
export const EDGE_HANDLE_SLOT_COUNT = 6;

/** Fractional position (0–1) along a node side for each slot. */
export const EDGE_HANDLE_SLOT_OFFSETS = [0.16, 0.32, 0.48, 0.52, 0.68, 0.84];

export function slottedHandleId(
  side: EdgeHandleSide,
  direction: "in" | "out",
  slot: number,
): string {
  const idx = Math.max(0, Math.min(EDGE_HANDLE_SLOT_COUNT - 1, slot));
  return `${side}-${direction}-${idx}`;
}

export type EdgeHandlePair = {
  sourceHandle: string;
  targetHandle: string;
  sourceSide: EdgeHandleSide;
  targetSide: EdgeHandleSide;
};

function nodeCenter(pos: { x: number; y: number }): { cx: number; cy: number } {
  return { cx: pos.x + NODE_W / 2, cy: pos.y + NODE_H / 2 };
}

/** Closest rectangle side toward a delta vector (uses node aspect ratio). */
export function sideFacingDelta(dx: number, dy: number): EdgeHandleSide {
  const ax = Math.abs(dx) * NODE_H;
  const ay = Math.abs(dy) * NODE_W;
  if (ax >= ay) {
    return dx >= 0 ? "right" : "left";
  }
  return dy >= 0 ? "bottom" : "top";
}

function oppositeSide(side: EdgeHandleSide): EdgeHandleSide {
  switch (side) {
    case "top":
      return "bottom";
    case "bottom":
      return "top";
    case "left":
      return "right";
    default:
      return "left";
  }
}

/** Pick exit/entry sides so each edge uses the shortest-facing pair on both rectangles. */
export function edgeSidesForLayout(
  sourceId: number,
  targetId: number,
  positions: Map<number, { x: number; y: number }>,
): { sourceSide: EdgeHandleSide; targetSide: EdgeHandleSide } {
  const src = positions.get(sourceId);
  const tgt = positions.get(targetId);
  if (!src || !tgt) {
    return { sourceSide: "right", targetSide: "left" };
  }

  const { cx: srcCx, cy: srcCy } = nodeCenter(src);
  const { cx: tgtCx, cy: tgtCy } = nodeCenter(tgt);
  const dx = tgtCx - srcCx;
  const dy = tgtCy - srcCy;

  const sourceSide = sideFacingDelta(dx, dy);
  const targetSide = sideFacingDelta(-dx, -dy);

  // Same-side degenerate (overlapping nodes): use opposite sides on the dominant axis.
  if (sourceSide === targetSide) {
    return { sourceSide, targetSide: oppositeSide(sourceSide) };
  }

  return { sourceSide, targetSide };
}

type HandleLayoutEdge = { source: number; target: number; key?: number | string };

/** Assign exit/entry side + slot for every edge incident on a node. */
function assignHandlesForNode(
  nodeId: number,
  edges: HandleLayoutEdge[],
  positions: Map<number, { x: number; y: number }>,
): Map<string, { side: EdgeHandleSide; slot: number }> {
  const result = new Map<string, { side: EdgeHandleSide; slot: number }>();
  const nodePos = positions.get(nodeId);
  if (!nodePos) return result;

  const { cx, cy } = nodeCenter(nodePos);
  type Incident = {
    edgeKey: string;
    role: "out" | "in";
    side: EdgeHandleSide;
    along: number;
  };
  const incident: Incident[] = [];

  for (const e of edges) {
    if (e.source === e.target) continue;
    const edgeKey = String(e.key ?? `${e.source}-${e.target}`);
    let peerId: number | null = null;
    let role: "out" | "in" | null = null;
    if (e.source === nodeId) {
      peerId = e.target;
      role = "out";
    } else if (e.target === nodeId) {
      peerId = e.source;
      role = "in";
    }
    if (peerId == null || role == null) continue;
    const peerPos = positions.get(peerId);
    if (!peerPos) continue;
    const { cx: px, cy: py } = nodeCenter(peerPos);
    const dx = px - cx;
    const dy = py - cy;
    const side = sideFacingDelta(dx, dy);
    const along = side === "left" || side === "right" ? py : px;
    incident.push({ edgeKey, role, side, along });
  }

  if (incident.length === 0) return result;

  const bySide = new Map<EdgeHandleSide, Incident[]>();
  for (const item of incident) {
    if (!bySide.has(item.side)) bySide.set(item.side, []);
    bySide.get(item.side)!.push(item);
  }

  for (const [, group] of bySide) {
    group.sort((a, b) => a.along - b.along);
    const n = group.length;
    group.forEach((item, idx) => {
      const slot =
        n <= 1
          ? 0
          : n <= EDGE_HANDLE_SLOT_COUNT
            ? idx
            : Math.floor((idx / (n - 1)) * (EDGE_HANDLE_SLOT_COUNT - 1));
      result.set(`${item.edgeKey}:${item.role}`, { side: item.side, slot });
    });
  }

  return result;
}

/** Spread handles across sides when a node fans out to many peers (mesh). */
export function edgeHandlePairsForGraph(
  edges: HandleLayoutEdge[],
  positions: Map<number, { x: number; y: number }>,
): Map<string, EdgeHandlePair> {
  const result = new Map<string, EdgeHandlePair>();
  const nodeIds = new Set<number>();
  for (const e of edges) {
    if (e.source === e.target) continue;
    nodeIds.add(e.source);
    nodeIds.add(e.target);
  }

  const bindingsByNode = new Map<number, Map<string, { side: EdgeHandleSide; slot: number }>>();
  for (const nodeId of nodeIds) {
    bindingsByNode.set(nodeId, assignHandlesForNode(nodeId, edges, positions));
  }

  for (const e of edges) {
    if (e.source === e.target) continue;
    const edgeKey = String(e.key ?? `${e.source}-${e.target}`);
    const srcBind = bindingsByNode.get(e.source)?.get(`${edgeKey}:out`);
    const tgtBind = bindingsByNode.get(e.target)?.get(`${edgeKey}:in`);
    const fallback = edgeSidesForLayout(e.source, e.target, positions);

    let sourceSide = srcBind?.side ?? fallback.sourceSide;
    let targetSide = tgtBind?.side ?? fallback.targetSide;
    const sourceSlot = srcBind?.slot ?? 0;
    const targetSlot = tgtBind?.slot ?? 0;

    if (sourceSide === targetSide) {
      targetSide = oppositeSide(sourceSide);
    }

    result.set(edgeKey, {
      sourceSide,
      targetSide,
      sourceHandle: slottedHandleId(sourceSide, "out", sourceSlot),
      targetHandle: slottedHandleId(targetSide, "in", targetSlot),
    });
  }

  return result;
}

export function edgeHandlesForLayout(
  sourceId: number,
  targetId: number,
  positions: Map<number, { x: number; y: number }>,
): { sourceHandle?: string; targetHandle?: string } {
  const { sourceSide, targetSide } = edgeSidesForLayout(sourceId, targetId, positions);
  return {
    sourceHandle: slottedHandleId(sourceSide, "out", 0),
    targetHandle: slottedHandleId(targetSide, "in", 0),
  };
}

export function edgeHandlePairForLayout(
  sourceId: number,
  targetId: number,
  positions: Map<number, { x: number; y: number }>,
): EdgeHandlePair {
  const { sourceSide, targetSide } = edgeSidesForLayout(sourceId, targetId, positions);
  return {
    sourceSide,
    targetSide,
    sourceHandle: slottedHandleId(sourceSide, "out", 0),
    targetHandle: slottedHandleId(targetSide, "in", 0),
  };
}

export function layoutEdgeCurvature(
  sourceId: number,
  targetId: number,
  positions: Map<number, { x: number; y: number }>,
  baseCurvature: number,
  handlePair?: Pick<EdgeHandlePair, "sourceSide" | "targetSide">,
): number {
  const src = positions.get(sourceId);
  const tgt = positions.get(targetId);
  if (!src || !tgt) return baseCurvature;

  const { cx: srcCx, cy: srcCy } = nodeCenter(src);
  const { cx: tgtCx, cy: tgtCy } = nodeCenter(tgt);
  const dx = tgtCx - srcCx;
  const dy = tgtCy - srcCy;
  const absDx = Math.abs(dx);
  const absDy = Math.abs(dy);

  const sides = handlePair ?? edgeSidesForLayout(sourceId, targetId, positions);
  const vertical = sides.sourceSide === "top" || sides.sourceSide === "bottom";

  if (vertical) {
    if (absDx > NODE_W * 0.35) {
      return dx > 0 ? 0.24 : -0.24;
    }
    if (absDy > NODE_H * 0.45) {
      return dy > 0 ? 0.22 : -0.22;
    }
    return baseCurvature * 0.75;
  }

  if (absDy > NODE_H * 0.45) {
    return dy > 0 ? 0.28 : -0.28;
  }
  if (absDy > NODE_H * 0.15) {
    return dy > 0 ? 0.18 : -0.18;
  }

  return baseCurvature * 0.85;
}

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
): void {
  const peerIds = spokePeerNodeIds(hubId, edges);
  if (peerIds.size < 2) return;

  const sorted = [...peerIds].sort((a, b) => {
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

/** Spread handles across four sides when a node fans out to many peers (mesh). */
export function edgeHandlePairsForGraph(
  edges: HandleLayoutEdge[],
  positions: Map<number, { x: number; y: number }>,
): Map<string, EdgeHandlePair> {
  const result = new Map<string, EdgeHandlePair>();
  const bySource = new Map<number, HandleLayoutEdge[]>();

  for (const e of edges) {
    if (e.source === e.target) continue;
    const key = String(e.key ?? `${e.source}-${e.target}`);
    if (!bySource.has(e.source)) bySource.set(e.source, []);
    bySource.get(e.source)!.push({ ...e, key });
  }

  for (const e of edges) {
    if (e.source === e.target) continue;
    const key = String(e.key ?? `${e.source}-${e.target}`);
    const base = edgeSidesForLayout(e.source, e.target, positions);
    result.set(key, {
      sourceSide: base.sourceSide,
      targetSide: base.targetSide,
      sourceHandle: `${base.sourceSide}-out`,
      targetHandle: `${base.targetSide}-in`,
    });
  }

  for (const [, outEdges] of bySource) {
    if (outEdges.length < 3) continue;

    const nodeId = outEdges[0]?.source;
    if (nodeId == null) continue;
    const pos = positions.get(nodeId);
    if (!pos) continue;
    const { cx, cy } = nodeCenter(pos);

    const ranked = outEdges
      .map((e) => {
        const tgt = positions.get(e.target);
        if (!tgt) return null;
        const { cx: tx, cy: ty } = nodeCenter(tgt);
        return { edge: e, angle: Math.atan2(ty - cy, tx - cx) };
      })
      .filter((x): x is { edge: HandleLayoutEdge; angle: number } => x != null)
      .sort((a, b) => a.angle - b.angle);

    const sides: EdgeHandleSide[] = ["right", "bottom", "left", "top"];
    ranked.forEach(({ edge, angle }) => {
      const key = String(edge.key ?? `${edge.source}-${edge.target}`);
      const sector = Math.floor(((angle + Math.PI) / (2 * Math.PI)) * 4) % 4;
      const spreadSide = sides[sector];
      const tgtPos = positions.get(edge.target);
      if (!tgtPos) return;
      const { cx: tx, cy: ty } = nodeCenter(tgtPos);
      const targetSide = sideFacingDelta(cx - tx, cy - ty);

      result.set(key, {
        sourceSide: spreadSide,
        targetSide,
        sourceHandle: `${spreadSide}-out`,
        targetHandle: `${targetSide}-in`,
      });
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
    sourceHandle: `${sourceSide}-out`,
    targetHandle: `${targetSide}-in`,
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
    sourceHandle: `${sourceSide}-out`,
    targetHandle: `${targetSide}-in`,
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

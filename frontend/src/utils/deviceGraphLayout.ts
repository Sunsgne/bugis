/** Force-directed + compact hub layout for device topology graphs. */

export type LayoutGraphNode = { id: number; site_id?: number | null };
export type LayoutGraphEdge = { source: number; target: number };

const NODE_W = 220;
const NODE_H = 72;

type SimNode = { x: number; y: number; vx: number; vy: number; siteId: number };

function siteKey(siteId?: number | null): number {
  return siteId ?? -1;
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

/** Prefer horizontal handles when source is left of target. */
export function edgeHandlesForLayout(
  sourceId: number,
  targetId: number,
  positions: Map<number, { x: number; y: number }>,
): { sourceHandle?: string; targetHandle?: string } {
  const src = positions.get(sourceId);
  const tgt = positions.get(targetId);
  if (!src || !tgt) return {};
  const srcCx = src.x + NODE_W / 2;
  const tgtCx = tgt.x + NODE_W / 2;
  if (tgtCx - srcCx > NODE_W * 0.4) {
    return { sourceHandle: "right", targetHandle: "left" };
  }
  if (srcCx - tgtCx > NODE_W * 0.4) {
    return { sourceHandle: "left", targetHandle: "right" };
  }
  const srcCy = src.y + NODE_H / 2;
  const tgtCy = tgt.y + NODE_H / 2;
  if (tgtCy > srcCy + NODE_H * 0.25) {
    return { sourceHandle: "bottom", targetHandle: "top" };
  }
  if (tgtCy < srcCy - NODE_H * 0.25) {
    return { sourceHandle: "top", targetHandle: "bottom" };
  }
  return {};
}

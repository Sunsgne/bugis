/** Force-directed layout: devices as nodes, links as edges (no site swimlanes). */

export type LayoutGraphNode = { id: number; site_id?: number | null };
export type LayoutGraphEdge = { source: number; target: number };

type SimNode = { x: number; y: number; vx: number; vy: number; siteId: number };

const NODE_W = 220;
const NODE_H = 64;
const MIN_DIST = NODE_W * 1.05;

function siteKey(siteId?: number | null): number {
  return siteId ?? -1;
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
  const orbitR = Math.min(width, height) * 0.34;

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
    const clusterR = Math.min(orbitR * 0.45, 40 + members.length * 28);
    members.forEach((n, idx) => {
      const angle =
        members.length === 1
          ? 0
          : (2 * Math.PI * idx) / members.length - Math.PI / 2;
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

/**
 * Compute device positions for a network graph (devices ↔ links).
 * Returns center coordinates for each device node card (220×64).
 */
export function layoutDeviceGraph(
  nodes: LayoutGraphNode[],
  edges: LayoutGraphEdge[],
  width: number,
  height: number,
): Map<number, { x: number; y: number }> {
  if (!nodes.length) return new Map();

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

  const iterations = linkPairs.length > 0 ? 140 : 40;
  const idealLen = Math.min(width, height) * 0.38;
  const repulsion = 9200;
  const spring = 0.042;
  const damping = 0.82;

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
      n.vx += (cx - n.x) * 0.004 * cooling;
      n.vy += (cy - n.y) * 0.004 * cooling;
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
      n.x = Math.max(NODE_W / 2 + 16, Math.min(width - NODE_W / 2 - 16, n.x));
      n.y = Math.max(NODE_H / 2 + 16, Math.min(height - NODE_H / 2 - 16, n.y));
    }
  }

  const pad = 24;
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
  const scale = Math.min(
    (width - pad * 2) / spanX,
    (height - pad * 2) / spanY,
    1.35,
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

export function siteLabelForNode(
  siteId: number | null | undefined,
  sites: { id: number; code: string; name: string }[],
): string | null {
  if (siteId == null) return null;
  const s = sites.find((x) => x.id === siteId);
  return s ? s.code : null;
}

import type { EChartsOption } from "echarts";
import { labelForOption, DEVICE_ROLE_OPTIONS } from "../constants/formOptions";
import { chartFont, chartText, utilColor, vendorColors } from "./theme";
import type { Topology } from "../api/types";

const EDGE_STYLE = {
  dci: { color: "#ef4444", width: 2.5, type: "dashed" as const },
  intra_dc: { color: "#ff6600", width: 2, type: "solid" as const },
  access: { color: "#10b981", width: 1.5, type: "solid" as const },
  uplink: { color: "#8b5cf6", width: 2, type: "solid" as const },
} as const;

type EdgeStyleKey = keyof typeof EDGE_STYLE;

function edgeStyle(type: string) {
  if (type in EDGE_STYLE) return EDGE_STYLE[type as EdgeStyleKey];
  return EDGE_STYLE.intra_dc;
}

const EDGE_LABEL: Record<string, string> = {
  dci: "DCI 互联",
  intra_dc: "Fabric 内链路",
  access: "接入",
  uplink: "上行",
};

const VNI_PALETTE = ["#ff6600", "#10b981", "#8b5cf6", "#06b6d4", "#ec4899", "#eab308"];

export type OverlayTopo = {
  nodes: { id: number; name: string; vtep_ip: string; vnis: number[]; status: string }[];
  edges: { vni: number; source: number; target: number }[];
  vnis: number[];
};

export type OverlayTopoOptions = {
  /** When set, only members of this VNI and their tunnels are drawn. */
  selectedVni?: number | null;
};

export type VniMemberSummary = {
  vni: number;
  deviceCount: number;
  devices: { id: number; name: string; vtep_ip: string; status: string }[];
};

/** Build VNI → device membership index for search / filter panels. */
export function buildVniMemberIndex(topo: OverlayTopo | null | undefined): VniMemberSummary[] {
  if (!topo?.nodes?.length) return [];
  const byVni = new Map<number, VniMemberSummary["devices"]>();
  for (const node of topo.nodes) {
    for (const vni of node.vnis ?? []) {
      const list = byVni.get(vni) ?? [];
      list.push({
        id: node.id,
        name: node.name,
        vtep_ip: node.vtep_ip,
        status: node.status,
      });
      byVni.set(vni, list);
    }
  }
  return Array.from(byVni.entries())
    .map(([vni, devices]) => ({
      vni,
      deviceCount: devices.length,
      devices: devices.sort((a, b) => a.name.localeCompare(b.name)),
    }))
    .sort((a, b) => a.vni - b.vni);
}

function fmtG(mbps: number): string {
  return mbps >= 1000 ? `${(mbps / 1000).toFixed(0)}G` : `${mbps}M`;
}

function roleLabel(role: string): string {
  return labelForOption(DEVICE_ROLE_OPTIONS, role);
}

/** Physical fabric / DCI topology with site columns and interactive roam. */
export function physicalTopologyOption(topo: Topology): EChartsOption {
  const NO_SITE = -1;
  const siteColumns = [
    ...topo.sites.map((s) => ({ id: s.id, label: `${s.code} · ${s.name}` })),
    ...(topo.nodes.some((n) => !n.site_id) ? [{ id: NO_SITE, label: "未分配站点" }] : []),
  ];

  const categories = siteColumns.map((s, i) => ({
    name: s.label,
    itemStyle: {
      color: i === siteColumns.length - 1 && s.id === NO_SITE ? "#94a3b8" : "#ff6600",
    },
  }));

  const colW = 260;
  const rowH = 96;
  const marginX = 100;
  const marginY = 88;

  const nodeById = new Map(topo.nodes.map((n) => [n.id, n]));
  const graphNodes = topo.nodes.map((n) => {
    const colIdx = siteColumns.findIndex((s) => s.id === (n.site_id ?? NO_SITE));
    const col = Math.max(colIdx, 0);
    const row = topo.nodes.filter((m) => (m.site_id ?? NO_SITE) === (n.site_id ?? NO_SITE)).indexOf(n);
    const vendorColor = vendorColors[n.vendor] || "#64748b";
    const online = n.status === "online";
    return {
      id: String(n.id),
      name: n.name,
      category: col,
      x: marginX + col * colW,
      y: marginY + row * rowH,
      symbol: "roundRect",
      symbolSize: [128, 46],
      itemStyle: {
        color: "#ffffff",
        borderColor: vendorColor,
        borderWidth: 2,
        shadowBlur: 8,
        shadowColor: "rgba(15, 23, 42, 0.08)",
      },
      label: {
        show: true,
        formatter: `{title|${n.name}}\n{meta|${n.vendor.toUpperCase()} · ${roleLabel(n.role)}}`,
        rich: {
          title: { fontSize: 12, fontWeight: 700, color: chartText.primary, lineHeight: 18 },
          meta: { fontSize: 10, color: chartText.secondary, lineHeight: 16 },
        },
      },
      tooltip: {
        formatter: () =>
          `<b>${n.name}</b><br/>厂商 ${n.vendor.toUpperCase()} · ${roleLabel(n.role)}<br/>` +
          `Overlay ${n.overlay_tech.replace("_", "-").toUpperCase()}<br/>` +
          `状态 ${online ? "在线" : n.status}`,
      },
      emphasis: {
        itemStyle: { borderWidth: 3, shadowBlur: 16, shadowColor: "rgba(255, 102, 0, 0.35)" },
      },
    };
  });

  const links = topo.edges
    .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
    .map((e) => {
      const style = edgeStyle(e.type);
      const util = e.utilization_pct ?? (e.capacity_mbps ? (e.reserved_mbps / e.capacity_mbps) * 100 : 0);
      return {
        source: String(e.source),
        target: String(e.target),
        name: e.name,
        lineStyle: {
          color: style.color,
          width: style.width,
          type: style.type,
          curveness: e.type === "dci" ? 0.22 : 0.08,
          opacity: 0.85,
        },
        label: {
          show: true,
          formatter: `${fmtG(e.capacity_mbps)} · ${util.toFixed(0)}%`,
          fontSize: 10,
          color: utilColor(util),
          backgroundColor: "rgba(255,255,255,0.92)",
          padding: [2, 6],
          borderRadius: 4,
        },
        emphasis: { lineStyle: { width: style.width + 1.5, opacity: 1 } },
      };
    });

  const height =
    marginY +
    Math.max(
      1,
      ...siteColumns.map(
        (s) => topo.nodes.filter((n) => (n.site_id ?? NO_SITE) === s.id).length,
      ),
    ) *
      rowH +
    60;

  void height;

  return {
    animationDuration: 600,
    animationEasing: "cubicOut",
    tooltip: { trigger: "item", backgroundColor: chartText.tooltipBg, borderColor: chartText.tooltipBorder, textStyle: { color: "#e2e8f0", fontSize: 12 } },
    legend: {
      data: siteColumns.map((s) => s.label),
      type: "scroll",
      bottom: 8,
      textStyle: { color: chartText.secondary, fontFamily: chartFont, fontSize: 11 },
    },
    series: [
      {
        type: "graph",
        layout: "none",
        roam: true,
        scaleLimit: { min: 0.45, max: 2.5 },
        categories,
        data: graphNodes,
        links,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [0, 8],
        lineStyle: { opacity: 0.85 },
        emphasis: { focus: "adjacency", lineStyle: { width: 4 } },
        blur: { itemStyle: { opacity: 0.25 }, lineStyle: { opacity: 0.12 } },
      },
    ],
  };
}

/** EVPN overlay graph — edges are only drawn when a VNI is selected (scalable). */
export function overlayTopologyOption(
  topo: OverlayTopo | null | undefined,
  options?: OverlayTopoOptions,
): EChartsOption | null {
  if (!topo?.nodes?.length) return null;

  const selectedVni = options?.selectedVni ?? null;

  const visibleNodes =
    selectedVni != null
      ? topo.nodes.filter((n) => (n.vnis ?? []).includes(selectedVni))
      : topo.nodes;

  const visibleNodeIds = new Set(visibleNodes.map((n) => n.id));

  const visibleEdges =
    selectedVni != null
      ? topo.edges.filter(
          (e) =>
            e.vni === selectedVni &&
            visibleNodeIds.has(e.source) &&
            visibleNodeIds.has(e.target),
        )
      : [];

  const vniColor = (vni: number) =>
    VNI_PALETTE[(topo.vnis.indexOf(vni) + VNI_PALETTE.length) % VNI_PALETTE.length];

  const accent = selectedVni != null ? vniColor(selectedVni) : "#059669";

  const n = visibleNodes.length;
  const cx = 420;
  const cy = 280;
  const r = Math.min(220, 90 + n * 24);

  const graphNodes = visibleNodes.map((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(n, 1) - Math.PI / 2;
    const up = node.status === "up";
    const vniCount = node.vnis?.length ?? 0;
    return {
      id: String(node.id),
      name: node.name,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
      symbol: "circle",
      symbolSize: selectedVni != null ? 62 : 54,
      itemStyle: {
        color: up ? (selectedVni != null ? `${accent}22` : "#d1fae5") : "#f1f5f9",
        borderColor: up ? accent : "#94a3b8",
        borderWidth: selectedVni != null ? 3 : 2,
        shadowBlur: 12,
        shadowColor: up ? `${accent}55` : "rgba(148, 163, 184, 0.2)",
      },
      label: {
        show: true,
        position: "bottom" as const,
        distance: 10,
        formatter:
          selectedVni != null
            ? `{name|${node.name}}\n{ip|${node.vtep_ip}}`
            : `{name|${node.name}}\n{ip|${node.vtep_ip}}\n{vnis|${vniCount} VNI}`,
        rich: {
          name: { fontSize: 11, fontWeight: 700, color: chartText.primary, lineHeight: 16 },
          ip: { fontSize: 10, color: chartText.secondary, lineHeight: 14 },
          vnis: { fontSize: 9, color: chartText.muted, lineHeight: 14 },
        },
      },
      tooltip: {
        formatter: () => {
          const vniText =
            selectedVni != null
              ? `VNI ${selectedVni}`
              : `VNI ${(node.vnis ?? []).slice(0, 12).join(", ")}${
                  vniCount > 12 ? ` … +${vniCount - 12}` : ""
                }`;
          return (
            `<b>${node.name}</b><br/>VTEP ${node.vtep_ip}<br/>` +
            `${vniText}<br/>状态 ${up ? "Up" : node.status}`
          );
        },
      },
    };
  });

  const nodePos = Object.fromEntries(
    graphNodes.map((gn) => [gn.id, { x: gn.x as number, y: gn.y as number }]),
  );

  const links = visibleEdges.map((e, idx) => {
    const color = vniColor(e.vni);
    const a = nodePos[String(e.source)];
    const b = nodePos[String(e.target)];
    const curveness = a && b ? (e.source < e.target ? 0.18 : -0.18) : 0.12;
    return {
      id: `e-${idx}`,
      source: String(e.source),
      target: String(e.target),
      value: e.vni,
      lineStyle: {
        color,
        width: 2.5,
        type: "dashed" as const,
        curveness,
        opacity: 0.88,
      },
      emphasis: { lineStyle: { width: 4, opacity: 1 } },
      label: {
        show: visibleEdges.length <= 8,
        formatter: `VNI ${e.vni}`,
        fontSize: 10,
        color,
      },
    };
  });

  const legend =
    selectedVni != null
      ? {
          data: [`VNI ${selectedVni}`],
          bottom: 8,
          textStyle: { color: chartText.secondary, fontFamily: chartFont },
        }
      : undefined;

  return {
    animationDuration: 600,
    animationEasing: "cubicOut",
    tooltip: {
      trigger: "item",
      backgroundColor: chartText.tooltipBg,
      borderColor: chartText.tooltipBorder,
      textStyle: { color: "#e2e8f0", fontSize: 12 },
    },
    legend,
    graphic:
      selectedVni == null && topo.vnis.length > 0
        ? [
            {
              type: "text",
              left: "center",
              top: "middle",
              style: {
                text: "选择右侧 VNI 查看隧道互联",
                fill: chartText.muted,
                fontSize: 13,
                fontFamily: chartFont,
              },
              silent: true,
            },
          ]
        : undefined,
    series: [
      {
        type: "graph",
        layout: "none",
        roam: true,
        scaleLimit: { min: 0.45, max: 2.4 },
        data: graphNodes,
        links,
        emphasis: { focus: "adjacency" },
        edgeSymbol: ["circle", "arrow"],
        edgeSymbolSize: [3, 9],
        blur: { itemStyle: { opacity: 0.2 }, lineStyle: { opacity: 0.08 } },
      },
    ],
  };
}

export { EDGE_LABEL, VNI_PALETTE };

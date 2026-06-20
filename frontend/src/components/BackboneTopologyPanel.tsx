import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  MarkerType,
  MiniMap,
  ReactFlow,
  getBezierPath,
  useReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  applyNodeChanges,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Progress,
  Row,
  Segmented,
  Space,
  Statistic,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { ClearOutlined, SearchOutlined } from "@ant-design/icons";
import { labelForOption, DEVICE_ROLE_OPTIONS } from "@/constants/formOptions";
import { vendorColors } from "@/charts/theme";
import type { LinkUsage, Topology } from "@/api/types";
import { useTc } from "@/i18n/useTc";
import { backboneUtilColor, fmtLinkBw, linkUtilizationLines } from "@/utils/linkUtilization";
import { layoutDeviceGraph, siteLabelForNode } from "@/utils/deviceGraphLayout";
import {
  curvatureForEdge,
  linkEdgeShortLabel,
  mergeTopologyEdges,
  utilizationMarker,
} from "@/utils/topologyEdges";
import LinkUtilizationTooltipContent from "./LinkUtilizationTooltipContent";
import InterfaceNameCell from "./InterfaceNameCell";
import LogicalPeerEdge from "./LogicalPeerEdge";
import TopologyLayoutControls from "./TopologyLayoutControls";
import { useTopologyLayout } from "@/hooks/useTopologyLayout";
import type { TopologyNodePositions } from "./PhysicalTopologyFlow";

type UtilTier = "all" | "healthy" | "warning" | "critical";

type EdgeData = {
  link?: LinkUsage;
  utilization_pct: number;
  shortLabel: string;
  highlighted?: boolean;
  curvature?: number;
};

function shortHost(name: string, max = 26): string {
  if (name.length <= max) return name;
  const head = Math.ceil((max - 1) / 2);
  const tail = max - head - 1;
  return `${name.slice(0, head)}…${name.slice(-tail)}`;
}

function DeviceNode({
  data,
}: {
  data: {
    label: string;
    fullName: string;
    meta: string;
    siteLabel?: string | null;
    border: string;
    online: boolean;
    dimmed?: boolean;
  };
}) {
  return (
    <div
      className="device-graph-node rounded-xl border-2 bg-white px-3 py-2.5 shadow-sm transition-all hover:shadow-md"
      style={{
        borderColor: data.border,
        width: 220,
        opacity: data.dimmed ? 0.35 : 1,
      }}
      title={data.fullName}
    >
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${data.online ? "bg-emerald-500" : "bg-slate-300"}`} />
        <span className="truncate text-sm font-semibold text-slate-800">{data.label}</span>
        {data.siteLabel && (
          <span className="ml-auto shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
            {data.siteLabel}
          </span>
        )}
      </div>
      <div className="mt-1 truncate text-[11px] text-slate-500">{data.meta}</div>
    </div>
  );
}

function UtilizationEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
  markerEnd,
}: EdgeProps) {
  const { tc } = useTc();
  const d = data as EdgeData | undefined;
  const pct = d?.utilization_pct ?? 0;
  const color = backboneUtilColor(pct);
  const link = d?.link;
  const [labelHover, setLabelHover] = useState(false);
  const [edgeHover, setEdgeHover] = useState(false);
  const showTooltip = Boolean(link && (edgeHover || labelHover || d?.highlighted));
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature: d?.curvature ?? 0.25,
  });

  return (
    <>
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={24}
        className="react-flow__edge-interaction backbone-edge-hit"
        onMouseEnter={() => setEdgeHover(true)}
        onMouseLeave={() => setEdgeHover(false)}
      />
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: color,
          strokeWidth: selected ? 4 : 2 + Math.min(pct / 40, 2.5),
          opacity: selected ? 1 : 0.92,
        }}
      />
      <EdgeLabelRenderer>
        <Tooltip
          open={showTooltip}
          placement="top"
          mouseEnterDelay={0.12}
          overlayStyle={{ maxWidth: 420 }}
          title={link ? <LinkUtilizationTooltipContent link={link} pct={pct} tc={tc} /> : undefined}
        >
          <div
            className="backbone-edge-label nodrag nopan"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              borderColor: color,
            }}
            onMouseEnter={() => setLabelHover(true)}
            onMouseLeave={() => setLabelHover(false)}
          >
            {d?.shortLabel ?? ""}
          </div>
        </Tooltip>
      </EdgeLabelRenderer>
    </>
  );
}

const nodeTypes = { device: DeviceNode };
const edgeTypes = { utilization: UtilizationEdge, logicalPeer: LogicalPeerEdge };

function FitViewOnLayout({ layoutKey, skip }: { layoutKey: string; skip?: boolean }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    if (skip) return;
    const timer = window.setTimeout(() => {
      fitView({ padding: 0.1, maxZoom: 1.05, duration: 320 });
    }, 80);
    return () => window.clearTimeout(timer);
  }, [fitView, layoutKey, skip]);
  return null;
}

function buildFilteredTopo(topo: Topology, links: LinkUsage[]): Topology {
  if (!links.length) {
    return { ...topo, edges: [] };
  }
  const deviceIds = new Set<number>();
  for (const l of links) {
    deviceIds.add(l.device_a_id);
    deviceIds.add(l.device_z_id);
  }
  return {
    sites: topo.sites,
    nodes: topo.nodes.filter((n) => deviceIds.has(n.id)),
    edges: links.map((l) => ({
      id: l.link_id,
      name: l.name,
      type: l.type,
      source: l.device_a_id,
      target: l.device_z_id,
      capacity_mbps: l.capacity_mbps,
      reserved_mbps: l.reserved_mbps,
      utilization_pct: l.utilization_pct,
    })),
  };
}

function buildLayout(
  topo: Topology,
  size: { w: number; h: number },
  linksById: Map<number, LinkUsage>,
  savedPositions: TopologyNodePositions,
  tc: (zh: string) => string,
  highlightLinkId?: number | null,
  highlightDeviceId?: number | null,
): { nodes: Node[]; edges: Edge[] } {
  const autoPositions = layoutDeviceGraph(
    topo.nodes.map((n) => ({ id: n.id, site_id: n.site_id })),
    topo.edges.map((e) => ({ source: e.source, target: e.target })),
    size.w,
    size.h,
  );

  const connectedDevices = new Set<number>();
  for (const e of topo.edges) {
    connectedDevices.add(e.source);
    connectedDevices.add(e.target);
  }
  if (highlightLinkId != null) {
    const link = linksById.get(highlightLinkId);
    if (link) {
      connectedDevices.add(link.device_a_id);
      connectedDevices.add(link.device_z_id);
    }
  }

  const highlightSet = new Set<number>();
  if (highlightDeviceId != null) {
    highlightSet.add(highlightDeviceId);
    for (const id of connectedDevices) highlightSet.add(id);
  } else if (highlightLinkId != null) {
    for (const id of connectedDevices) highlightSet.add(id);
  }

  const dimActive = highlightSet.size > 0;

  const nodes: Node[] = topo.nodes.map((n) => {
    const saved = savedPositions[String(n.id)];
    const pos = saved ?? autoPositions.get(n.id) ?? { x: 0, y: 0 };
    const vendorColor = vendorColors[n.vendor] || "#64748b";
    const dimmed = dimActive ? !highlightSet.has(n.id) : false;

    return {
      id: String(n.id),
      type: "device",
      position: pos,
      data: {
        label: shortHost(n.name),
        fullName: n.name,
        siteLabel: siteLabelForNode(n.site_id, topo.sites),
        meta: `${n.vendor.toUpperCase()} · ${labelForOption(DEVICE_ROLE_OPTIONS, n.role)}`,
        border: vendorColor,
        online: n.status === "online",
        dimmed,
      },
    };
  });

  const nodeIds = new Set(topo.nodes.map((n) => String(n.id)));
  const utilizationEdges: Edge[] = topo.edges
    .filter((e) => nodeIds.has(String(e.source)) && nodeIds.has(String(e.target)))
    .map((e, i) => {
      const link = linksById.get(e.id) ?? linksById.get(Number(e.id));
      const pct = link?.utilization_pct ?? e.utilization_pct ?? 0;
      const selected = highlightLinkId != null && link?.link_id === highlightLinkId;
      const color = backboneUtilColor(pct);
      return {
        id: `e-${link?.link_id ?? i}`,
        source: String(e.source),
        target: String(e.target),
        type: "utilization",
        animated: pct >= 85,
        selected,
        interactionWidth: 24,
        data: {
          link,
          utilization_pct: pct,
          shortLabel: link ? linkEdgeShortLabel(link, pct) : `${fmtLinkBw(e.capacity_mbps)} · ${Math.round(pct)}%`,
          curvature: curvatureForEdge(topo.edges, e.id),
        } satisfies EdgeData,
        markerEnd: utilizationMarker(pct),
        style: { stroke: color },
      };
    });

  const links = [...linksById.values()];
  const edges = mergeTopologyEdges(utilizationEdges, links, nodeIds, tc);

  return { nodes, edges };
}

function tierMatch(pct: number, tier: UtilTier): boolean {
  if (tier === "all") return true;
  if (tier === "healthy") return pct < 50;
  if (tier === "warning") return pct >= 50 && pct < 85;
  return pct >= 85;
}

type Props = {
  topo: Topology | null;
  links: LinkUsage[];
  loading?: boolean;
};

export default function BackboneTopologyPanel({ topo, links, loading }: Props) {
  const { tc } = useTc();
  const layout = useTopologyLayout();
  const hostRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 960, h: 480 });
  const [panelSearch, setPanelSearch] = useState("");
  const [utilTier, setUtilTier] = useState<UtilTier>("all");
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | null>(null);
  const [hoveredLink, setHoveredLink] = useState<LinkUsage | null>(null);

  useEffect(() => {
    void layout.loadLayout();
  }, []);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    const apply = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setSize({ w: rect.width, h: rect.height });
      }
    };
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const linksById = useMemo(() => new Map(links.map((l) => [l.link_id, l])), [links]);

  const panelFilteredLinks = useMemo(() => {
    const q = panelSearch.trim().toLowerCase();
    return links.filter((l) => {
      if (typeFilter && l.type !== typeFilter) return false;
      if (!tierMatch(l.utilization_pct ?? 0, utilTier)) return false;
      if (!q) return true;
      return (
        l.name.toLowerCase().includes(q) ||
        l.device_a.toLowerCase().includes(q) ||
        l.device_z.toLowerCase().includes(q) ||
        (l.supplier || "").toLowerCase().includes(q) ||
        `${l.site_a_code || ""} ${l.site_z_code || ""}`.toLowerCase().includes(q)
      );
    });
  }, [links, panelSearch, utilTier, typeFilter]);

  const graphTopo = useMemo(
    () => (topo ? buildFilteredTopo(topo, panelFilteredLinks) : null),
    [topo, panelFilteredLinks],
  );

  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(
    () =>
      graphTopo
        ? buildLayout(
            graphTopo,
            size,
            linksById,
            layout.draftPositions,
            tc,
            selectedLinkId,
            selectedDeviceId,
          )
        : { nodes: [], edges: [] },
    [graphTopo, size, linksById, layout.draftPositions, tc, selectedLinkId, selectedDeviceId],
  );

  const [flowNodes, setFlowNodes] = useState<Node[]>(layoutNodes);
  useEffect(() => {
    setFlowNodes(layoutNodes);
  }, [layoutNodes]);

  const hasSavedLayout = Object.keys(layout.draftPositions).length > 0;

  const edges = useMemo(
    () =>
      layoutEdges.map((e) => {
        const link = (e.data as EdgeData | undefined)?.link;
        return {
          ...e,
          interactionWidth: 24,
          data: {
            ...(e.data as EdgeData),
            highlighted: hoveredLink != null && link?.link_id === hoveredLink.link_id,
          },
        };
      }),
    [layoutEdges, hoveredLink],
  );

  const layoutKey = `${size.w}x${size.h}-${layoutNodes.length}-${edges.length}-${selectedLinkId}-${selectedDeviceId}`;

  const selectedLink = selectedLinkId != null ? linksById.get(selectedLinkId) : null;
  const detailLink = hoveredLink ?? selectedLink;

  const stats = useMemo(() => {
    const healthy = links.filter((l) => (l.utilization_pct ?? 0) < 50).length;
    const warning = links.filter((l) => {
      const p = l.utilization_pct ?? 0;
      return p >= 50 && p < 85;
    }).length;
    const critical = links.filter((l) => (l.utilization_pct ?? 0) >= 85).length;
    return { healthy, warning, critical, total: links.length };
  }, [links]);

  function clearSelection() {
    setSelectedLinkId(null);
    setSelectedDeviceId(null);
    setHoveredLink(null);
  }

  if (!topo && !loading) {
    return <Empty description={tc("拓扑数据加载失败，将自动重试…")} />;
  }

  return (
    <div className="backbone-topology-panel">
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <div ref={hostRef} className="backbone-topology-canvas device-graph-flow">
            {graphTopo && graphTopo.nodes.length > 0 ? (
              <ReactFlow
                nodes={flowNodes}
                edges={edges}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                nodesDraggable
                nodesConnectable={false}
                elementsSelectable
                onNodesChange={(changes: NodeChange[]) => {
                  setFlowNodes((current) => applyNodeChanges(changes, current));
                }}
                onNodeDragStop={(_, node) => {
                  setFlowNodes((current) => {
                    const next: TopologyNodePositions = {};
                    for (const n of current) {
                      next[n.id] = n.id === node.id ? node.position : n.position;
                    }
                    next[node.id] = node.position;
                    layout.handlePositionsChange(next, { autoSave: layout.autoSave });
                    return current.map((n) => (n.id === node.id ? { ...n, position: node.position } : n));
                  });
                }}
                onNodeClick={(_, node) => {
                  if (node.type === "device") {
                    setSelectedDeviceId(Number(node.id));
                    setSelectedLinkId(null);
                  }
                }}
                onEdgeClick={(_, edge) => {
                  const link = (edge.data as EdgeData | undefined)?.link;
                  if (link) {
                    setSelectedLinkId(link.link_id);
                    setSelectedDeviceId(null);
                  }
                }}
                onEdgeMouseEnter={(_, edge) => {
                  const link = (edge.data as EdgeData | undefined)?.link;
                  if (link) setHoveredLink(link);
                }}
                onEdgeMouseLeave={() => setHoveredLink(null)}
                onPaneClick={clearSelection}
                panOnDrag
                zoomOnScroll
                minZoom={0.45}
                maxZoom={1.5}
                proOptions={{ hideAttribution: true }}
              >
                <FitViewOnLayout layoutKey={layoutKey} skip={hasSavedLayout} />
                <Background gap={20} size={1} color="#e2e8f0" />
                <Controls showInteractive={false} position="bottom-right" />
                <MiniMap
                  nodeStrokeWidth={2}
                  zoomable
                  pannable
                  className="backbone-topology-minimap"
                  position="bottom-left"
                />
              </ReactFlow>
            ) : (
              <div className="backbone-topology-empty">
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={
                    panelFilteredLinks.length === 0 && links.length > 0
                      ? tc("无匹配链路")
                      : tc("暂无骨干链路 · 点击「配置骨干链路」智能推荐或手动选配")
                  }
                />
              </div>
            )}

            <div className="backbone-topology-layout-bar">
              <TopologyLayoutControls
                compact
                layoutDirty={layout.layoutDirty}
                saving={layout.saving}
                autoSave={layout.autoSave}
                onAutoSaveChange={layout.toggleAutoSave}
                onSave={() => layout.saveLayout()}
                onReset={() => layout.resetLayout()}
              />
            </div>

            <div className="backbone-topology-hint">
              {tc("滚轮缩放 · 拖拽平移")} · {graphTopo?.nodes.length ?? 0} {tc("台设备")} ·{" "}
              {panelFilteredLinks.length} {tc("条链路")}
            </div>

            <div className="backbone-topology-legend">
              <span className="backbone-legend-item">
                <span className="backbone-legend-dot" style={{ background: "#22c55e" }} />
                &lt;50%
              </span>
              <span className="backbone-legend-item">
                <span className="backbone-legend-dot" style={{ background: "#f59e0b" }} />
                50–84%
              </span>
              <span className="backbone-legend-item">
                <span className="backbone-legend-dot" style={{ background: "#ef4444" }} />
                ≥85%
              </span>
              <span className="backbone-legend-item">
                <span
                  className="backbone-legend-line"
                  style={{ background: "transparent", borderTop: "2px dashed #64748b", width: 18, height: 0 }}
                />
                {tc("同链路对端")}
              </span>
            </div>
          </div>
        </Col>

        <Col xs={24} xl={8}>
          <div className="backbone-topology-sidebar">
            <Typography.Text strong>{tc("检索")}</Typography.Text>
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder={tc("搜索链路 / 设备 / 供应商 / 站点")}
              value={panelSearch}
              onChange={(e) => setPanelSearch(e.target.value)}
              style={{ marginTop: 8 }}
            />
            <Segmented
              block
              style={{ marginTop: 10 }}
              value={utilTier}
              onChange={(v) => setUtilTier(v as UtilTier)}
              options={[
                { label: `${tc("全部")} (${stats.total})`, value: "all" },
                { label: `<50% (${stats.healthy})`, value: "healthy" },
                { label: `50–84% (${stats.warning})`, value: "warning" },
                { label: `≥85% (${stats.critical})`, value: "critical" },
              ]}
            />
            <Segmented
              block
              style={{ marginTop: 8 }}
              value={typeFilter ?? "all"}
              onChange={(v) => setTypeFilter(v === "all" ? undefined : (v as string))}
              options={[
                { label: tc("全部"), value: "all" },
                { label: tc("跨站点 DCI"), value: "dci" },
                { label: tc("站内互联"), value: "intra_dc" },
              ]}
            />
            {(selectedLinkId != null || selectedDeviceId != null || hoveredLink) && (
              <Button
                size="small"
                icon={<ClearOutlined />}
                onClick={clearSelection}
                style={{ marginTop: 8 }}
              >
                {tc("清除筛选")}
              </Button>
            )}

            <Row gutter={8} style={{ marginTop: 16 }}>
              <Col span={8}>
                <Statistic title="<50%" value={stats.healthy} valueStyle={{ color: "#22c55e", fontSize: 18 }} />
              </Col>
              <Col span={8}>
                <Statistic title="50–84%" value={stats.warning} valueStyle={{ color: "#f59e0b", fontSize: 18 }} />
              </Col>
              <Col span={8}>
                <Statistic title="≥85%" value={stats.critical} valueStyle={{ color: "#ef4444", fontSize: 18 }} />
              </Col>
            </Row>

            {detailLink ? (
              <Card size="small" className="backbone-topology-detail" style={{ marginTop: 12 }}>
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  <Space wrap>
                    <Typography.Text strong>{detailLink.name}</Typography.Text>
                    <Tag color={detailLink.type === "dci" ? "blue" : "green"}>{detailLink.type}</Tag>
                  </Space>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {detailLink.device_a} ↔ {detailLink.device_z}
                  </Typography.Text>
                  {(detailLink.interface_a || detailLink.interface_z) && (
                    <Space direction="vertical" size={2} style={{ width: "100%" }}>
                      {detailLink.interface_a ? (
                        <InterfaceNameCell name={detailLink.interface_a} copyable={false} />
                      ) : null}
                      {detailLink.interface_z ? (
                        <InterfaceNameCell name={detailLink.interface_z} copyable={false} />
                      ) : null}
                    </Space>
                  )}
                  <Progress
                    percent={Math.round(detailLink.utilization_pct ?? 0)}
                    strokeColor={backboneUtilColor(detailLink.utilization_pct ?? 0)}
                    size="small"
                  />
                  {linkUtilizationLines(detailLink, detailLink.utilization_pct ?? 0, tc).map((line) => (
                    <Typography.Text key={line} type="secondary" style={{ fontSize: 12, display: "block" }}>
                      {line}
                    </Typography.Text>
                  ))}
                </Space>
              </Card>
            ) : null}

            <Typography.Text strong style={{ display: "block", marginTop: 16 }}>
              {tc("链路")} ({panelFilteredLinks.length})
            </Typography.Text>
            <div className="backbone-link-list">
              {panelFilteredLinks.map((l) => {
                const pct = l.utilization_pct ?? 0;
                const active = selectedLinkId === l.link_id;
                return (
                  <button
                    key={l.link_id}
                    type="button"
                    className={`backbone-link-list-item${active ? " is-active" : ""}`}
                    onClick={() => {
                      setSelectedLinkId(l.link_id);
                      setSelectedDeviceId(null);
                    }}
                    onMouseEnter={() => setHoveredLink(l)}
                    onMouseLeave={() => setHoveredLink((h) => (h?.link_id === l.link_id ? null : h))}
                  >
                    <div className="backbone-link-list-head">
                      <span className="backbone-link-list-name">{l.name}</span>
                      <Badge
                        count={`${Math.round(pct)}%`}
                        style={{ backgroundColor: backboneUtilColor(pct) }}
                      />
                    </div>
                    <div className="backbone-link-list-meta">
                      {shortHost(l.device_a, 18)} → {shortHost(l.device_z, 18)}
                    </div>
                    <Progress
                      percent={Math.round(pct)}
                      showInfo={false}
                      strokeColor={backboneUtilColor(pct)}
                      size="small"
                    />
                  </button>
                );
              })}
            </div>
          </div>
        </Col>
      </Row>
    </div>
  );
}

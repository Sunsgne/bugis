import {
  Alert,
  Descriptions,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ForwardingPath, LinkUsage, Topology } from "../api/types";
import MultipointEvpnDiagram from "./MultipointEvpnDiagram";
import PhysicalTopologyFlow from "./PhysicalTopologyFlow";
import { useTc } from "@/i18n/useTc";
import { filterLinksForPath, filterTopologyForPath } from "@/utils/topologyPathFilter";

const COMPARISON_COLORS: Record<string, string> = {
  match: "green",
  partial: "orange",
  mismatch: "red",
  no_probe: "default",
};

const LAYER_LABELS: Record<string, string> = {
  access: "接入",
  evpn_encap: "EVPN 封装",
  evpn_tunnel: "EVPN 隧道",
  evpn_instance: "EVPN 实例",
};

type Props = {
  circuitId: number;
  circuitCode?: string;
};

export default function CircuitForwardingPathPanel({ circuitId, circuitCode }: Props) {
  const { tc } = useTc();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<ForwardingPath | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [topo, setTopo] = useState<Topology | null>(null);
  const [links, setLinks] = useState<LinkUsage[]>([]);
  const [activeTab, setActiveTab] = useState("business");
  const [topoLoading, setTopoLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data: body } = await api.get<ForwardingPath>(`/circuits/${circuitId}/forwarding-path`);
      setData(body);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : tc("加载转发路径失败"));
    } finally {
      setLoading(false);
    }
  }, [circuitId, tc]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setActiveTab("business");
    setTopo(null);
    setLinks([]);
  }, [circuitId]);

  useEffect(() => {
    const hl = data?.underlay?.topology_highlight;
    if (activeTab !== "underlay" || !hl?.device_ids?.length) return;

    let cancelled = false;
    setTopoLoading(true);
    (async () => {
      try {
        const [topoRes, linksRes] = await Promise.all([
          api.get<Topology>("/capacity/topology"),
          api.get<LinkUsage[]>("/capacity/links/usage"),
        ]);
        if (!cancelled) {
          const multipoint = hl.mode === "multipoint";
          setTopo(
            filterTopologyForPath(topoRes.data, hl.device_ids, hl.link_ids || [], {
              multipoint,
            }),
          );
          setLinks(filterLinksForPath(linksRes.data, hl.link_ids || [], { multipoint }));
        }
      } catch {
        if (!cancelled) {
          setTopo(null);
          setLinks([]);
        }
      } finally {
        if (!cancelled) setTopoLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    activeTab,
    data?.underlay?.topology_highlight?.device_ids,
    data?.underlay?.topology_highlight?.link_ids,
  ]);

  const highlightPath = useMemo(
    () => ({
      deviceIds: data?.underlay?.topology_highlight?.device_ids,
      linkIds: data?.underlay?.topology_highlight?.link_ids,
    }),
    [data?.underlay?.topology_highlight],
  );

  const pathTopo = useMemo(() => {
    if (!topo || !highlightPath.deviceIds?.length) return null;
    if (topo.nodes.length === 0) return null;
    return topo;
  }, [topo, highlightPath.deviceIds?.length]);

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <Spin tip={tc("加载转发路径…")} />
      </div>
    );
  }

  if (error || !data) {
    return <Alert type="error" showIcon message={error || tc("无数据")} />;
  }

  const underlay = data.underlay;
  const comparison = underlay.comparison;
  const comparisonColor = COMPARISON_COLORS[comparison?.status || "no_probe"] || "default";
  const isMultipoint =
    data.business_plane.topology === "multipoint" || underlay.topology_mode === "multipoint";
  const topologyHighlight = underlay.topology_highlight;
  const multipointOrder =
    isMultipoint && topologyHighlight?.endpoint_order?.length
      ? topologyHighlight.endpoint_order
      : undefined;
  const pathOrder =
    !isMultipoint && highlightPath.deviceIds?.length ? highlightPath.deviceIds : undefined;

  return (
    <div className="circuit-forwarding-path" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Space wrap>
        {isMultipoint ? (
          <Tag color="purple">
            {tc("多点接入")} · {data.business_plane.endpoint_count ?? data.business_plane.endpoints?.length ?? 0} PE
          </Tag>
        ) : null}
        <Tag color="geekblue">{data.path_mode === "explicit_sr" ? "SR 显式" : "IGP 自动"}</Tag>
        {underlay.igp_algorithm && (
          <Tag>{underlay.igp_algorithm === "dijkstra_igp_cost" ? "IGP Cost 最短路" : underlay.igp_algorithm}</Tag>
        )}
        {underlay.total_igp_cost != null && (
          <Tag color="purple">{tc("总 IGP Cost")}: {underlay.total_igp_cost}</Tag>
        )}
        {comparison && (
          <Tag color={comparisonColor}>
            {tc("算路/实测")}: {comparison.status}
          </Tag>
        )}
      </Space>

      {underlay.path_reason && (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {underlay.path_reason}
        </Typography.Text>
      )}

      {comparison?.note && (
        <Alert type="info" showIcon message={comparison.note} style={{ marginBottom: 4 }} />
      )}

      {underlay.connectivity_errors && underlay.connectivity_errors.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message={underlay.connectivity_errors.join("；")}
        />
      )}

      <Tabs
        size="small"
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "business",
            label: tc("业务面 (EVPN)"),
            children: (
              <div>
                <Descriptions size="small" bordered column={{ xs: 1, sm: 2, lg: 4 }} style={{ marginBottom: 12 }}>
                  <Descriptions.Item label="VNI">{data.business_plane.vni ?? "—"}</Descriptions.Item>
                  <Descriptions.Item label="VSI">{data.business_plane.vsi_name || "—"}</Descriptions.Item>
                  <Descriptions.Item label="RD">{data.business_plane.rd || "—"}</Descriptions.Item>
                  <Descriptions.Item label="RT">{data.business_plane.rt || "—"}</Descriptions.Item>
                </Descriptions>
                {isMultipoint && data.business_plane.endpoints?.length ? (
                  <MultipointEvpnDiagram
                    vni={data.business_plane.vni}
                    vsi_name={data.business_plane.vsi_name}
                    rd={data.business_plane.rd}
                    rt={data.business_plane.rt}
                    endpoints={data.business_plane.endpoints}
                  />
                ) : null}
                <Table
                  size="small"
                  rowKey={(r) => `${r.sequence}-${r.layer}`}
                  pagination={false}
                  dataSource={data.business_plane.hops || []}
                  columns={[
                    { title: "#", dataIndex: "sequence", width: 48 },
                    {
                      title: tc("层级"),
                      dataIndex: "layer",
                      width: 100,
                      render: (v: string) => LAYER_LABELS[v] || v,
                    },
                    {
                      title: tc("设备"),
                      render: (_, r) => r.device_name || r.source_device || r.target_device || "—",
                    },
                    {
                      title: tc("详情"),
                      dataIndex: "detail",
                      ellipsis: true,
                    },
                  ]}
                />
              </div>
            ),
          },
          {
            key: "control",
            label: tc("控制面"),
            children: (
              <div>
                <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
                  {data.control_plane.note}
                </Typography.Paragraph>
                <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                  {tc("VTEP 注册")}
                </Typography.Text>
                <Table
                  size="small"
                  rowKey={(r) => String(r.device_id)}
                  pagination={false}
                  dataSource={data.control_plane.vteps || []}
                  style={{ marginBottom: 16 }}
                  columns={[
                    { title: tc("端点"), dataIndex: "endpoint_label", width: 56 },
                    { title: tc("设备"), dataIndex: "device_name" },
                    { title: "VTEP IP", dataIndex: "vtep_ip" },
                    {
                      title: tc("状态"),
                      dataIndex: "status",
                      render: (s: string) => (
                        <Tag color={s === "up" ? "green" : undefined}>{s}</Tag>
                      ),
                    },
                    {
                      title: tc("服务 VNI"),
                      render: (_, r) => (
                        <Tag color={r.serves_circuit_vni ? "blue" : undefined}>
                          {r.serves_circuit_vni ? tc("是") : tc("否")}
                        </Tag>
                      ),
                    },
                  ]}
                />
                <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                  {tc("EVPN 路由")} ({data.control_plane.route_count ?? 0})
                </Typography.Text>
                <Table
                  size="small"
                  rowKey={(_, i) => String(i)}
                  pagination={data.control_plane.routes?.length > 8 ? { pageSize: 8 } : false}
                  dataSource={data.control_plane.routes || []}
                  columns={[
                    { title: tc("类型"), dataIndex: "route_type", width: 120 },
                    { title: "VNI", dataIndex: "vni", width: 72 },
                    { title: tc("下一跳"), dataIndex: "next_hop", ellipsis: true },
                    { title: "VTEP", dataIndex: "vtep_ip", ellipsis: true },
                    { title: "RD", dataIndex: "rd", ellipsis: true },
                  ]}
                />
              </div>
            ),
          },
          {
            key: "underlay",
            label: tc("Underlay"),
            children: (
              <div>
                {topoLoading ? (
                  <div style={{ height: 320, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16 }}>
                    <Spin tip={tc("加载路径拓扑…")} />
                  </div>
                ) : pathTopo && highlightPath.deviceIds?.length ? (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                      <Typography.Text strong>
                        {isMultipoint ? tc("接入 PE 站点") : tc("拓扑路径高亮")}
                      </Typography.Text>
                      <Link to={`/topology?highlight_circuit=${circuitId}`}>{tc("在拓扑页打开")}</Link>
                    </div>
                    <div className="circuit-path-topology-wrap">
                      <PhysicalTopologyFlow
                        topo={pathTopo}
                        links={links}
                        savedPositions={{}}
                        highlightPath={highlightPath}
                        pathDeviceOrder={pathOrder}
                        multipointDeviceOrder={multipointOrder}
                        fillContainer
                        className="circuit-path-topology-mini"
                      />
                    </div>
                  </div>
                ) : highlightPath.deviceIds?.length ? (
                  <Alert
                    type="warning"
                    showIcon
                    style={{ marginBottom: 16 }}
                    message={tc("路径设备未出现在容量拓扑中，请确认骨干链路已配置")}
                  />
                ) : null}
                <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                  {isMultipoint ? tc("接入 PE 站点") : tc("IGP 计算路径")}
                </Typography.Text>
                <Space wrap style={{ marginBottom: 12 }}>
                  {(underlay.computed?.hops || []).map((h, i) => (
                    <Tag
                      key={h.device_id}
                      color={
                        isMultipoint
                          ? "blue"
                          : i === 0
                            ? "blue"
                            : i === (underlay.computed?.hops?.length || 0) - 1
                              ? "purple"
                              : "geekblue"
                      }
                    >
                      {isMultipoint && h.endpoint_label ? `${h.endpoint_label} · ` : ""}
                      {h.name}
                      {!isMultipoint && h.igp_cost != null && i < (underlay.computed?.hops?.length || 0) - 1
                        ? ` → cost ${h.igp_cost}`
                        : ""}
                    </Tag>
                  ))}
                  {!isMultipoint && underlay.segment_list && underlay.segment_list.length > 0 && (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      SID: {underlay.segment_list.join(" → ")}
                    </Typography.Text>
                  )}
                </Space>
                {!isMultipoint ? (
                <Table
                  size="small"
                  rowKey={(r) => String(r.sequence)}
                  pagination={false}
                  dataSource={underlay.computed?.segments || []}
                  style={{ marginBottom: 16 }}
                  columns={[
                    { title: "#", dataIndex: "sequence", width: 48, render: (v) => v + 1 },
                    {
                      title: tc("链路"),
                      render: (_, r) => r.link_name || (r.connected ? tc("已连接") : tc("无链路")),
                    },
                    {
                      title: tc("出接口"),
                      dataIndex: "interface",
                      render: (v) => v || "—",
                    },
                    {
                      title: "IGP Cost",
                      dataIndex: "igp_cost",
                      render: (v, r) => (
                        v != null ? (
                          <span>
                            {v}
                            {!r.cost_learned && (
                              <Typography.Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>
                                ({tc("默认")})
                              </Typography.Text>
                            )}
                          </span>
                        ) : "—"
                      ),
                    },
                    {
                      title: tc("实测 RTT"),
                      dataIndex: "probe_segment_rtt_ms",
                      render: (v, r) => {
                        if (v == null) return "—";
                        const loss = r.probe_loss_pct;
                        return (
                          <span>
                            {v} ms
                            {loss != null && loss > 0 && (
                              <Tag color="red" style={{ marginLeft: 4 }}>{loss}%</Tag>
                            )}
                          </span>
                        );
                      },
                    },
                  ]}
                />
                ) : (
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                    message={tc("多点 EVPN 无单一 Underlay 路径")}
                    description={tc("各 PE 通过 EVPN 控制面加入同一 VNI，Underlay 仅展示接入站点位置。")}
                  />
                )}

                <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                  {tc("拨测实测")}
                </Typography.Text>
                {underlay.probed?.available ? (
                  <>
                    <Space wrap style={{ marginBottom: 12 }}>
                      <Tag color={underlay.probed.reachable ? "green" : "red"}>
                        {underlay.probed.reachable ? tc("可达") : tc("不可达")}
                      </Tag>
                      {underlay.probed.rtt_ms != null && (
                        <Tag>{tc("端到端 RTT")} {underlay.probed.rtt_ms} ms</Tag>
                      )}
                      {underlay.probed.probe_method && (
                        <Tag>{underlay.probed.probe_method}</Tag>
                      )}
                      {underlay.probed.probed_at && (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {underlay.probed.probed_at}
                        </Typography.Text>
                      )}
                    </Space>
                    <Table
                      size="small"
                      rowKey="hop"
                      pagination={false}
                      dataSource={underlay.probed.hops || []}
                      columns={[
                        { title: tc("跳"), dataIndex: "hop", width: 48 },
                        { title: tc("设备"), dataIndex: "device" },
                        { title: tc("目标"), dataIndex: "target", ellipsis: true },
                        {
                          title: tc("段 RTT"),
                          dataIndex: "segment_rtt_ms",
                          render: (v) => (v != null ? `${v} ms` : "—"),
                        },
                        {
                          title: tc("累计 RTT"),
                          dataIndex: "rtt_ms",
                          render: (v) => (v != null ? `${v} ms` : "—"),
                        },
                        {
                          title: tc("丢包"),
                          dataIndex: "packet_loss_pct",
                          render: (v) => (v != null ? `${v}%` : "—"),
                        },
                        {
                          title: tc("状态"),
                          dataIndex: "status",
                          render: (s: string) => (
                            <Tag color={s === "up" ? "green" : "red"}>{s}</Tag>
                          ),
                        },
                      ]}
                    />
                  </>
                ) : (
                  <Alert
                    type="info"
                    showIcon
                    message={underlay.probed?.note || tc("尚无拨测记录")}
                  />
                )}
              </div>
            ),
          },
        ]}
      />

      {circuitCode && (
        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
          {tc("生成于")} {data.generated_at}
        </Typography.Text>
      )}
    </div>
  );
}

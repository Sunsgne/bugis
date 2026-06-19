import { useMemo, useState } from "react";
import {
  Button,
  Col,
  Empty,
  Input,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import { ClearOutlined, SearchOutlined } from "@ant-design/icons";
import TopologyGraph from "./TopologyGraph";
import { useTc } from "@/i18n/useTc";
import {
  buildVniMemberIndex,
  overlayTopologyOption,
  platformVniSetFromInventory,
  type OverlayTopo,
  type VniMemberSummary,
} from "../charts/topologyGraph";

const { Text } = Typography;

type VniScope = "all" | "platform";

type OverlayInventory = {
  items?: Array<{ vni?: number | null; source?: string }>;
};

type Props = {
  topo: OverlayTopo | null | undefined;
  overlayInventory?: OverlayInventory | null;
};

export default function OverlayTopologyPanel({ topo, overlayInventory }: Props) {
  const { tc } = useTc();
  const [selectedVni, setSelectedVni] = useState<number | undefined>(undefined);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number | undefined>(undefined);
  const [search, setSearch] = useState("");
  const [vniScope, setVniScope] = useState<VniScope>("all");

  const platformVnis = useMemo(
    () => platformVniSetFromInventory(overlayInventory),
    [overlayInventory],
  );

  const vniIndex = useMemo(
    () => buildVniMemberIndex(topo, platformVnis),
    [topo, platformVnis],
  );

  const scopedVnis = useMemo(() => {
    if (vniScope === "platform") {
      return vniIndex.filter((row) => row.platformManaged);
    }
    return vniIndex;
  }, [vniIndex, vniScope]);

  const filteredVnis = useMemo(() => {
    const q = search.trim();
    if (!q) return scopedVnis;
    return scopedVnis.filter((row) => String(row.vni).includes(q));
  }, [scopedVnis, search]);

  const selectedRow = useMemo(
    () => (selectedVni != null ? vniIndex.find((r) => r.vni === selectedVni) : undefined),
    [vniIndex, selectedVni],
  );

  const selectedDevice = useMemo(
    () => (selectedDeviceId != null ? topo?.nodes?.find((n) => n.id === selectedDeviceId) : undefined),
    [topo, selectedDeviceId],
  );

  const deviceVnis = useMemo(() => {
    if (!selectedDevice) return [];
    const deviceVniSet = new Set(selectedDevice.vnis ?? []);
    return scopedVnis.filter((row) => deviceVniSet.has(row.vni));
  }, [selectedDevice, scopedVnis]);

  const chartOpt = useMemo(
    () =>
      topo?.nodes?.length
        ? overlayTopologyOption(topo, {
            selectedVni,
            highlightDeviceId: selectedVni == null ? selectedDeviceId : undefined,
          })
        : null,
    [topo, selectedVni, selectedDeviceId],
  );

  function clearFilters() {
    setSelectedVni(undefined);
    setSelectedDeviceId(undefined);
    setSearch("");
  }

  function selectVni(vni: number) {
    setSelectedVni(vni);
  }

  function selectDevice(deviceId: number | undefined) {
    setSelectedDeviceId(deviceId);
    setSelectedVni(undefined);
  }

  if (!topo?.nodes?.length || !chartOpt) {
    return <Empty description={tc('Overlay 尚未建立 · 开通控制器托管专线后自动呈现')} />;
  }

  const tunnelCount =
    selectedVni != null
      ? topo.edges.filter((e) => e.vni === selectedVni).length
      : topo.edges.length;

  const deviceOptions = topo.nodes
    .map((n) => ({
      value: n.id,
      label: `${n.name} · ${(n.vnis ?? []).length} VNI`,
    }))
    .sort((a, b) => a.label.localeCompare(b.label));

  const hasActiveFilter = selectedVni != null || selectedDeviceId != null || search.length > 0;

  return (
    <div className="overlay-topology-panel">
      <Row gutter={16}>
        <Col xs={24} lg={16}>
          <Space style={{ marginBottom: 8 }} wrap>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {tc("滚轮缩放 · 拖拽平移")}
              {selectedVni != null
                ? ` · ${tc("当前 VNI")} ${selectedVni} · ${selectedRow?.deviceCount ?? 0} ${tc("台设备")} · ${tunnelCount} ${tc("条隧道")}`
                : selectedDevice
                  ? ` · ${tc("设备")} ${selectedDevice.name} · ${deviceVnis.length} ${tc("个 VNI")}`
                  : ` · ${topo.nodes.length} ${tc("台设备")} · ${scopedVnis.length} ${tc("个 VNI")} · ${tc("选择 VNI 查看隧道")}`}
            </Text>
            {hasActiveFilter && (
              <Button size="small" icon={<ClearOutlined />} onClick={clearFilters}>{tc('清除筛选')}</Button>
            )}
          </Space>
          <TopologyGraph option={chartOpt} height={520} />
        </Col>

        <Col xs={24} lg={8}>
          <div className="overlay-vni-sidebar">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <div>
                <Text strong>{tc('检索')}</Text>
                <Select
                  showSearch
                  allowClear
                  placeholder={tc('按设备反查 VNI')}
                  style={{ width: "100%", marginTop: 8 }}
                  value={selectedDeviceId}
                  onChange={(v) => selectDevice(v ?? undefined)}
                  optionFilterProp="label"
                  options={deviceOptions}
                />
                <Select
                  showSearch
                  allowClear
                  placeholder={tc('输入或选择 VNI')}
                  style={{ width: "100%", marginTop: 8 }}
                  value={selectedVni}
                  onChange={(v) => {
                    setSelectedVni(v ?? undefined);
                    if (v != null) setSelectedDeviceId(undefined);
                  }}
                  optionFilterProp="label"
                  options={scopedVnis.map((row) => ({
                    value: row.vni,
                    label: `VNI ${row.vni} · ${row.deviceCount} ${tc("台")}${row.platformManaged ? ` · ${tc("平台")}` : ""}`,
                  }))}
                />
                <Input
                  allowClear
                  prefix={<SearchOutlined />}
                  placeholder={tc('按号码筛选 VNI 列表')}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  style={{ marginTop: 8 }}
                />
                <Segmented
                  block
                  style={{ marginTop: 8 }}
                  value={vniScope}
                  onChange={(v) => setVniScope(v as VniScope)}
                  options={[
                    { label: `${tc("全部")} (${vniIndex.length})`, value: "all" },
                    { label: `${tc("平台纳管")} (${platformVnis.size})`, value: "platform" },
                  ]}
                />
              </div>

              <Row gutter={8}>
                <Col span={8}>
                  <Statistic title="VNI" value={scopedVnis.length} valueStyle={{ fontSize: 18 }} />
                </Col>
                <Col span={8}>
                  <Statistic title={tc('设备')} value={topo.nodes.length} valueStyle={{ fontSize: 18 }} />
                </Col>
                <Col span={8}>
                  <Statistic
                    title={tc('隧道')}
                    value={selectedVni != null ? tunnelCount : "—"}
                    valueStyle={{ fontSize: 18 }}
                  />
                </Col>
              </Row>

              {selectedRow ? (
                <div>
                  <Space wrap style={{ marginBottom: 4 }}>
                    <Text strong>VNI {selectedRow.vni}</Text>
                    {selectedRow.platformManaged && <Tag color="blue">{tc('平台纳管')}</Tag>}
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12, display: "block" }}>
                    {tc("关联设备")} ({selectedRow.deviceCount})
                  </Text>
                  <Table
                    className="overlay-vni-device-table"
                    size="small"
                    rowKey="id"
                    pagination={false}
                    style={{ marginTop: 8 }}
                    dataSource={selectedRow.devices}
                    scroll={{ y: 140 }}
                    columns={[
                      {
                        title: tc('设备'),
                        dataIndex: "name",
                        ellipsis: true,
                        render: (name: string, row: { id: number }) => (
                          <Button
                            type="link"
                            size="small"
                            style={{ padding: 0, height: "auto" }}
                            onClick={() => selectDevice(row.id)}
                          >
                            <Text ellipsis title={name}>{name}</Text>
                          </Button>
                        ),
                      },
                      {
                        title: "VTEP",
                        dataIndex: "vtep_ip",
                        width: 100,
                        ellipsis: true,
                      },
                      {
                        title: tc('状态'),
                        dataIndex: "status",
                        width: 56,
                        render: (s: string) => (
                          <Tag color={s === "up" ? "green" : "default"}>{s}</Tag>
                        ),
                      },
                    ]}
                  />
                  {selectedRow.deviceCount < 2 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>{tc('单点 VNI，无设备间隧道。')}</Text>
                  )}
                </div>
              ) : selectedDevice ? (
                <div>
                  <Text strong>{selectedDevice.name}</Text>
                  <Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: 4 }}>
                    VTEP {selectedDevice.vtep_ip} · {tc("承载")} {deviceVnis.length} {tc("个 VNI")}
                  </Text>
                  <Table
                    className="overlay-vni-list-table"
                    size="small"
                    rowKey="vni"
                    style={{ marginTop: 8 }}
                    dataSource={deviceVnis}
                    pagination={deviceVnis.length > 10 ? { pageSize: 10, size: "small" } : false}
                    scroll={{ y: 240 }}
                    onRow={(row) => ({
                      onClick: () => selectVni(row.vni),
                      style: { cursor: "pointer" },
                    })}
                    columns={[
                      {
                        title: "VNI",
                        dataIndex: "vni",
                        width: 90,
                        render: (v: number, row: VniMemberSummary) => (
                          <Space size={4}>
                            <Text strong>{v}</Text>
                            {row.platformManaged && <Tag color="blue" style={{ margin: 0 }}>{tc('平台')}</Tag>}
                          </Space>
                        ),
                      },
                      {
                        title: tc('设备数'),
                        dataIndex: "deviceCount",
                        width: 100,
                        align: "right",
                      },
                      {
                        title: tc('对端'),
                        dataIndex: "devices",
                        ellipsis: true,
                        render: (devices: { name: string; id: number }[]) => {
                          const peers = devices
                            .filter((d) => d.id !== selectedDevice.id)
                            .map((d) => d.name);
                          const preview = peers.slice(0, 2).join(", ");
                          const more = peers.length > 2 ? ` +${peers.length - 2}` : "";
                          return (
                            <Text type="secondary" ellipsis title={peers.join(", ") || tc("无对端")}>
                              {preview || "—"}
                              {more}
                            </Text>
                          );
                        },
                      },
                    ]}
                  />
                </div>
              ) : (
                <div>
                  <Text strong>{tc('VNI 列表')}</Text>
                  <Table
                    className="overlay-vni-list-table"
                    size="small"
                    rowKey="vni"
                    style={{ marginTop: 8 }}
                    dataSource={filteredVnis}
                    pagination={{
                      pageSize: 12,
                      size: "small",
                      showSizeChanger: true,
                      pageSizeOptions: ["12", "24", "48"],
                      showTotal: (total) => `${tc("共")} ${total}`,
                    }}
                    scroll={{ y: 260 }}
                    onRow={(row) => ({
                      onClick: () => selectVni(row.vni),
                      style: { cursor: "pointer" },
                    })}
                    columns={[
                      {
                        title: "VNI",
                        dataIndex: "vni",
                        width: 110,
                        sorter: (a: VniMemberSummary, b: VniMemberSummary) => a.vni - b.vni,
                        defaultSortOrder: "ascend",
                        render: (v: number, row: VniMemberSummary) => (
                          <Space size={4}>
                            <Text strong>{v}</Text>
                            {row.platformManaged && <Tag color="blue" style={{ margin: 0 }}>{tc('平台')}</Tag>}
                          </Space>
                        ),
                      },
                      {
                        title: tc('设备数'),
                        dataIndex: "deviceCount",
                        width: 100,
                        align: "right",
                        sorter: (a: VniMemberSummary, b: VniMemberSummary) => a.deviceCount - b.deviceCount,
                      },
                      {
                        title: tc('设备'),
                        dataIndex: "devices",
                        ellipsis: true,
                        render: (devices: { name: string }[]) => {
                          const names = devices.map((d) => d.name);
                          const preview = names.slice(0, 2).join(", ");
                          const more = names.length > 2 ? ` +${names.length - 2}` : "";
                          return (
                            <Text type="secondary" ellipsis title={names.join(", ")}>
                              {preview}
                              {more}
                            </Text>
                          );
                        },
                      },
                    ]}
                  />
                </div>
              )}
            </Space>
          </div>
        </Col>
      </Row>
    </div>
  );
}

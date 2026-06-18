import { useMemo, useState } from "react";
import {
  Button,
  Col,
  Empty,
  Input,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import { ClearOutlined, SearchOutlined } from "@ant-design/icons";
import TopologyGraph from "./TopologyGraph";
import {
  buildVniMemberIndex,
  overlayTopologyOption,
  type OverlayTopo,
} from "../charts/topologyGraph";

const { Text } = Typography;

type Props = {
  topo: OverlayTopo | null | undefined;
};

export default function OverlayTopologyPanel({ topo }: Props) {
  const [selectedVni, setSelectedVni] = useState<number | undefined>(undefined);
  const [search, setSearch] = useState("");

  const vniIndex = useMemo(() => buildVniMemberIndex(topo), [topo]);

  const filteredVnis = useMemo(() => {
    const q = search.trim();
    if (!q) return vniIndex;
    return vniIndex.filter((row) => String(row.vni).includes(q));
  }, [vniIndex, search]);

  const selectedRow = useMemo(
    () => (selectedVni != null ? vniIndex.find((r) => r.vni === selectedVni) : undefined),
    [vniIndex, selectedVni],
  );

  const chartOpt = useMemo(
    () => (topo?.nodes?.length ? overlayTopologyOption(topo, { selectedVni }) : null),
    [topo, selectedVni],
  );

  if (!topo?.nodes?.length || !chartOpt) {
    return <Empty description="Overlay 尚未建立 · 开通控制器托管专线后自动呈现" />;
  }

  const tunnelCount =
    selectedVni != null
      ? topo.edges.filter((e) => e.vni === selectedVni).length
      : topo.edges.length;

  return (
    <div className="overlay-topology-panel">
      <Row gutter={16}>
        <Col xs={24} lg={16}>
          <Space style={{ marginBottom: 8 }} wrap>
            <Text type="secondary" style={{ fontSize: 12 }}>
              滚轮缩放 · 拖拽平移
              {selectedVni != null
                ? ` · 当前 VNI ${selectedVni} · ${selectedRow?.deviceCount ?? 0} 台设备 · ${tunnelCount} 条隧道`
                : ` · ${topo.nodes.length} 台设备 · ${vniIndex.length} 个 VNI · 选择 VNI 查看隧道`}
            </Text>
            {selectedVni != null && (
              <Button
                size="small"
                icon={<ClearOutlined />}
                onClick={() => setSelectedVni(undefined)}
              >
                清除筛选
              </Button>
            )}
          </Space>
          <TopologyGraph option={chartOpt} height={520} />
        </Col>

        <Col xs={24} lg={8}>
          <div className="overlay-vni-sidebar">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <div>
                <Text strong>VNI 检索</Text>
                <Space.Compact style={{ width: "100%", marginTop: 8 }}>
                  <Select
                    showSearch
                    allowClear
                    placeholder="输入或选择 VNI"
                    style={{ flex: 1 }}
                    value={selectedVni}
                    onChange={(v) => setSelectedVni(v ?? undefined)}
                    optionFilterProp="label"
                    options={vniIndex.map((row) => ({
                      value: row.vni,
                      label: `VNI ${row.vni} · ${row.deviceCount} 台`,
                    }))}
                  />
                </Space.Compact>
                <Input
                  allowClear
                  prefix={<SearchOutlined />}
                  placeholder="按号码筛选列表"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  style={{ marginTop: 8 }}
                />
              </div>

              <Row gutter={8}>
                <Col span={8}>
                  <Statistic title="VNI" value={vniIndex.length} valueStyle={{ fontSize: 18 }} />
                </Col>
                <Col span={8}>
                  <Statistic title="设备" value={topo.nodes.length} valueStyle={{ fontSize: 18 }} />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="隧道"
                    value={selectedVni != null ? tunnelCount : "—"}
                    valueStyle={{ fontSize: 18 }}
                  />
                </Col>
              </Row>

              {selectedRow ? (
                <div>
                  <Text strong>
                    VNI {selectedRow.vni} 关联设备 ({selectedRow.deviceCount})
                  </Text>
                  <Table
                    className="overlay-vni-device-table"
                    size="small"
                    rowKey="id"
                    pagination={false}
                    style={{ marginTop: 8 }}
                    dataSource={selectedRow.devices}
                    scroll={{ y: 160 }}
                    columns={[
                      {
                        title: "设备",
                        dataIndex: "name",
                        ellipsis: true,
                        render: (name: string) => <Text ellipsis title={name}>{name}</Text>,
                      },
                      {
                        title: "VTEP",
                        dataIndex: "vtep_ip",
                        width: 110,
                        ellipsis: true,
                      },
                      {
                        title: "状态",
                        dataIndex: "status",
                        width: 64,
                        render: (s: string) => (
                          <Tag color={s === "up" ? "green" : "default"}>{s}</Tag>
                        ),
                      },
                    ]}
                  />
                  {selectedRow.deviceCount < 2 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      单点 VNI，无设备间隧道。
                    </Text>
                  )}
                </div>
              ) : (
                <div>
                  <Text strong>VNI 列表</Text>
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
                      showTotal: (total) => `共 ${total} 个`,
                    }}
                    scroll={{ y: 280 }}
                    onRow={(row) => ({
                      onClick: () => setSelectedVni(row.vni),
                      style: { cursor: "pointer" },
                    })}
                    columns={[
                      {
                        title: "VNI",
                        dataIndex: "vni",
                        width: 100,
                        sorter: (a, b) => a.vni - b.vni,
                        defaultSortOrder: "ascend",
                        render: (v: number) => <Text strong>VNI {v}</Text>,
                      },
                      {
                        title: "设备数",
                        dataIndex: "deviceCount",
                        width: 72,
                        align: "right",
                        sorter: (a, b) => a.deviceCount - b.deviceCount,
                      },
                      {
                        title: "设备",
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

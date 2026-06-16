import {
  BookOutlined,
  NodeIndexOutlined,
  RadarChartOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Drawer,
  Input,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  Device,
  DeviceInterface,
  DevicePortBinding,
  DevicePortBindings,
  SvidUsage,
} from "../api/types";
import SvidUsageCell from "./SvidUsageCell";
import AdoptBindingModal from "./AdoptBindingModal";
import InterfaceNameCell from "./InterfaceNameCell";
import {
  formatDiscoveredVia,
  formatInterfaceShort,
  formatInterfaceTooltip,
  formatOperStatus,
  formatVlanLabel,
} from "../utils/networkDisplay";

const BINDING_SOURCE: Record<string, { label: string; color: string }> = {
  platform: { label: "平台纳管", color: "blue" },
  device: { label: "现网占用", color: "orange" },
  legacy: { label: "手工", color: "red" },
};

const CIRCUIT_STATUS_COLOR: Record<string, string> = {
  active: "green",
  provisioning: "processing",
  pending: "gold",
  degraded: "orange",
  draft: "default",
  suspended: "default",
  terminated: "red",
};

function formatVlan(accessMode?: string, sVid?: number | null, cVid?: number | null) {
  return formatVlanLabel(accessMode, sVid, cVid);
}

function formatBandwidth(mbps?: number | null) {
  if (!mbps) return "—";
  return mbps >= 1000 ? `${mbps / 1000}G` : `${mbps}M`;
}

function formatPortSpeed(mbps?: number) {
  if (!mbps) return "—";
  return mbps >= 1000 ? `${mbps / 1000}G` : `${mbps}M`;
}

function formatCustomerLabel(row: DevicePortBinding) {
  if (row.tenant_name) {
    return row.tenant_code ? `${row.tenant_name} (${row.tenant_code})` : row.tenant_name;
  }
  return "未纳管";
}

interface DevicePortDrawerProps {
  device: Device | null;
  refreshVersion?: number;
  onClose: () => void;
  onCheck: (deviceId: number) => Promise<void>;
  onDiscover: (deviceId: number) => Promise<DeviceInterface[] | void>;
  onLearn: (device: Device) => Promise<void>;
}

export default function DevicePortDrawer({
  device,
  refreshVersion = 0,
  onClose,
  onCheck,
  onDiscover,
  onLearn,
}: DevicePortDrawerProps) {
  const [ifaces, setIfaces] = useState<DeviceInterface[]>([]);
  const [bindings, setBindings] = useState<DevicePortBindings | null>(null);
  const [ifacesLoading, setIfacesLoading] = useState(false);
  const [bindingsLoading, setBindingsLoading] = useState(false);
  const [ifaceSvidOnly, setIfaceSvidOnly] = useState(false);
  const [ifaceSearch, setIfaceSearch] = useState("");
  const [ifaceStatus, setIfaceStatus] = useState<"all" | "up" | "down" | "allocated">("all");
  const [activeTab, setActiveTab] = useState("ports");
  const [discovering, setDiscovering] = useState(false);
  const [adoptBinding, setAdoptBinding] = useState<DevicePortBinding | null>(null);

  async function loadBindings(deviceId: number, refresh = false) {
    setBindingsLoading(true);
    try {
      const { data } = await api.get<DevicePortBindings>(`/devices/${deviceId}/port-bindings`, {
        params: refresh ? { scan: true } : undefined,
      });
      setBindings(data);
    } finally {
      setBindingsLoading(false);
    }
  }

  async function loadIfaces(deviceId: number, refresh = false) {
    setIfacesLoading(true);
    try {
      const { data } = await api.get<DeviceInterface[]>(`/devices/${deviceId}/interfaces`, {
        params: refresh ? { scan: true } : undefined,
      });
      setIfaces(data);
      return data;
    } finally {
      setIfacesLoading(false);
    }
  }

  useEffect(() => {
    if (!device) {
      setIfaces([]);
      setBindings(null);
      setIfaceSearch("");
      setIfaceStatus("all");
      setIfaceSvidOnly(false);
      setActiveTab("ports");
      return;
    }

    let cancelled = false;
    (async () => {
      const [rows] = await Promise.all([
        loadIfaces(device.id, true),
        loadBindings(device.id, true),
      ]);
      if (cancelled || !rows) return;
      if (refreshVersion === 0 && rows.length === 0) {
        setDiscovering(true);
        try {
          const discovered = await onDiscover(device.id);
          if (!cancelled && Array.isArray(discovered)) {
            setIfaces(discovered);
          }
        } catch {
          // discover errors are surfaced by parent handler
        } finally {
          if (!cancelled) setDiscovering(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [device?.id, refreshVersion]);

  const ifaceHasSvid = ifaces.some((i) => (i.used_s_vids?.length ?? 0) > 0);

  const ifaceRows = useMemo(() => {
    const q = ifaceSearch.trim().toLowerCase();
    return ifaces.filter((iface) => {
      if (ifaceSvidOnly && !(iface.used_s_vids?.length ?? 0)) return false;
      if (ifaceStatus === "up" && iface.oper_status !== "up") return false;
      if (ifaceStatus === "down" && iface.oper_status === "up") return false;
      if (ifaceStatus === "allocated" && !iface.allocated) return false;
      if (!q) return true;
      return (
        iface.name.toLowerCase().includes(q) ||
        (iface.description || "").toLowerCase().includes(q)
      );
    });
  }, [ifaces, ifaceSvidOnly, ifaceSearch, ifaceStatus]);

  const ifaceSvidTotal = useMemo(
    () => ifaces.reduce((sum, i) => sum + (i.used_s_vids?.length ?? 0), 0),
    [ifaces],
  );

  async function refreshAll(refreshScan = true) {
    if (!device) return;
    await Promise.all([
      loadIfaces(device.id, refreshScan),
      loadBindings(device.id, refreshScan),
    ]);
  }

  return (
    <Drawer
      title={device ? `端口清单 · ${device.name}` : "端口清单"}
      width="min(96vw, 1320px)"
      open={!!device}
      onClose={onClose}
      destroyOnClose
      extra={
        device ? (
          <Space wrap>
            <Button size="small" icon={<RadarChartOutlined />} onClick={() => onCheck(device.id)}>
              检测 S-VID
            </Button>
            <Button
              size="small"
              icon={<NodeIndexOutlined />}
              loading={discovering}
              onClick={async () => {
                setDiscovering(true);
                try {
                  const data = await onDiscover(device.id);
                  if (Array.isArray(data)) setIfaces(data);
                  await loadBindings(device.id);
                } finally {
                  setDiscovering(false);
                }
              }}
            >
              SNMP 发现
            </Button>
            <Button size="small" icon={<BookOutlined />} onClick={() => onLearn(device)}>
              现网学习
            </Button>
            <Button size="small" type="link" onClick={() => refreshAll(true)}>
              刷新占用
            </Button>
          </Space>
        ) : null
      }
    >
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        物理端口来自 SNMP IF-MIB；客户接入绑定来自平台专线端点；S-VID 占用来自 running-config 与平台纳管合并。
        {device?.mgmt_ip_active ? (
          <>
            {" "}
            当前南向{" "}
            {device.mgmt_ip_active_role === "backup"
              ? device.mgmt_ip_backup_label || "备"
              : device.mgmt_ip_primary_label || "主"}{" "}
            {device.mgmt_ip_active}
            {device.mgmt_ip_backup ? "（主备自动切换）" : ""}。
          </>
        ) : device?.mgmt_ip_backup ? (
          <> 主 {device.mgmt_ip} / 备 {device.mgmt_ip_backup}，不可达时自动切换。</>
        ) : null}
      </Typography.Paragraph>

      {ifaces.some((i) => i.discovered_via === "snmp-sim") ? (
        <Alert
          type="warning"
          showIcon
          message="部分端口为模拟数据"
          description="snmp-sim 表示未从设备读到真实 IF-MIB。请确认 SNMP Community 与 UDP 161 可达后重新发现。"
          style={{ marginBottom: 12 }}
        />
      ) : null}

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: "ports",
            label: `物理端口 (${ifaces.length})`,
            children: (
              <>
                {!ifacesLoading && ifaces.length > 0 && !ifaceHasSvid ? (
                  <Alert
                    type="info"
                    showIcon
                    message="暂无 S-VID 占用数据"
                    description="请先执行「现网学习」拉取 running-config，再点「检测 S-VID」或「刷新占用」。"
                    style={{ marginBottom: 12 }}
                  />
                ) : null}

                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    alignItems: "center",
                    gap: 12,
                    marginBottom: 12,
                  }}
                >
                  <Input
                    allowClear
                    prefix={<SearchOutlined />}
                    placeholder="搜索接口名 / 描述"
                    value={ifaceSearch}
                    onChange={(e) => setIfaceSearch(e.target.value)}
                    style={{ width: 220 }}
                  />
                  <Select
                    value={ifaceStatus}
                    onChange={setIfaceStatus}
                    style={{ width: 140 }}
                    options={[
                      { value: "all", label: "全部状态" },
                      { value: "up", label: "仅 up" },
                      { value: "down", label: "仅 down" },
                      { value: "allocated", label: "仅有占用" },
                    ]}
                  />
                  {ifaceHasSvid ? (
                    <Space size={6}>
                      <Typography.Text type="secondary">
                        {ifaceSvidTotal} 个 S-VID · {ifaces.length} 个端口
                        {ifaceRows.length !== ifaces.length
                          ? ` · 筛选后 ${ifaceRows.length}`
                          : ""}
                      </Typography.Text>
                      <Typography.Text type="secondary">仅显示有占用</Typography.Text>
                      <Switch checked={ifaceSvidOnly} onChange={setIfaceSvidOnly} size="small" />
                    </Space>
                  ) : (
                    <Typography.Text type="secondary">
                      共 {ifaces.length} 个端口
                      {ifaceRows.length !== ifaces.length ? ` · 筛选后 ${ifaceRows.length}` : ""}
                    </Typography.Text>
                  )}
                </div>

                <Table
                  rowKey={(r) => `${r.device_id}-${r.name}`}
                  size="small"
                  loading={ifacesLoading || discovering}
                  dataSource={ifaceRows}
                  locale={{
                    emptyText: discovering
                      ? "SNMP 接口扫描中…（主备管理 IP 自动探测）"
                      : ifaceSvidOnly
                        ? "暂无 S-VID 占用端口"
                        : "暂无端口数据 · 将自动尝试 SNMP 发现",
                  }}
                  pagination={{
                    defaultPageSize: 50,
                    showSizeChanger: true,
                    pageSizeOptions: ["20", "50", "100", "200"],
                    showTotal: (total) => `共 ${total} 个端口`,
                  }}
                  scroll={{ x: 1080, y: "calc(100vh - 340px)" }}
                  columns={[
                    {
                      title: "接口",
                      dataIndex: "name",
                      width: 120,
                      fixed: "left",
                      render: (name: string) => <InterfaceNameCell name={name} />,
                    },
                    {
                      title: "描述",
                      dataIndex: "description",
                      width: 260,
                      ellipsis: { showTitle: false },
                      render: (d?: string) =>
                        d ? (
                          <Tooltip title={d}>
                            <span>{d}</span>
                          </Tooltip>
                        ) : (
                          "—"
                        ),
                    },
                    {
                      title: "速率",
                      dataIndex: "speed_mbps",
                      width: 72,
                      render: (s?: number) => formatPortSpeed(s),
                    },
                    {
                      title: "状态",
                      dataIndex: "oper_status",
                      width: 72,
                      render: (s?: string) => (
                        <Tag color={s === "up" ? "green" : "default"}>{formatOperStatus(s)}</Tag>
                      ),
                    },
                    {
                      title: "索引",
                      dataIndex: "ifindex",
                      width: 64,
                      render: (v?: number) => (v != null ? v : "—"),
                    },
                    {
                      title: "来源",
                      dataIndex: "discovered_via",
                      width: 96,
                      render: (d?: string) => (d ? <Tag>{formatDiscoveredVia(d)}</Tag> : "—"),
                    },
                    {
                      title: "S-VID 占用",
                      dataIndex: "used_s_vids",
                      width: 180,
                      render: (list?: SvidUsage[]) => <SvidUsageCell list={list} />,
                    },
                  ]}
                />
              </>
            ),
          },
          {
            key: "bindings",
            label: `客户·接口·业务 (${bindings?.total_bindings ?? 0})`,
            children: (
              <>
                <Alert
                  type="info"
                  showIcon
                  message="客户 · 接口 · 业务 关联关系"
                  description="每一行表示一个 S-VID 绑定：客户是谁、落在哪个物理口、承载哪条业务，以及端口限速带宽。"
                  style={{ marginBottom: 12 }}
                />

                {bindings ? (
                  <div style={{ marginBottom: 12 }}>
                    <Space wrap>
                      <Tag color="blue">平台纳管 {bindings.platform_bindings}</Tag>
                      <Tag color="orange">现网占用 {bindings.device_only_bindings}</Tag>
                      <Tag>已绑定接口 {bindings.bound_interfaces}</Tag>
                      <Tag color="green">空闲接口 {bindings.unbound_interfaces.length}</Tag>
                    </Space>
                  </div>
                ) : null}

                <Table<DevicePortBinding>
                  rowKey={(row) =>
                    `${row.interface_name}-${row.s_vid ?? "u"}-${row.c_vid ?? ""}-${row.circuit_id ?? row.business_name ?? row.source}`
                  }
                  size="small"
                  loading={bindingsLoading}
                  dataSource={bindings?.items ?? []}
                  locale={{ emptyText: "暂无关联关系 · 请先现网学习并刷新占用" }}
                  pagination={{
                    defaultPageSize: 50,
                    showSizeChanger: true,
                    pageSizeOptions: ["20", "50", "100"],
                    showTotal: (total) => `共 ${total} 条关联`,
                  }}
                  scroll={{ x: 1280, y: "calc(100vh - 360px)" }}
                  columns={[
                    {
                      title: "客户",
                      width: 160,
                      fixed: "left",
                      render: (_: unknown, row) =>
                        row.tenant_id ? (
                          <Link to={`/circuits?tenant=${row.tenant_id}`}>
                            {formatCustomerLabel(row)}
                          </Link>
                        ) : (
                          <Typography.Text type="secondary">{formatCustomerLabel(row)}</Typography.Text>
                        ),
                    },
                    {
                      title: "接口",
                      dataIndex: "interface_name",
                      width: 120,
                      render: (name: string) => <InterfaceNameCell name={name} />,
                    },
                    {
                      title: "业务",
                      dataIndex: "business_name",
                      width: 200,
                      ellipsis: true,
                      render: (v?: string, row?: DevicePortBinding) => (
                        <Tooltip title={row?.description || row?.circuit_code || row?.vsi_name}>
                          <span>{v || row?.vsi_name || row?.circuit_code || "—"}</span>
                        </Tooltip>
                      ),
                    },
                    {
                      title: "S-VID",
                      width: 120,
                      render: (_: unknown, row) => (
                        <Tag color={row.binding_type === "platform" ? "blue" : "orange"}>
                          {formatVlan(row.access_mode, row.s_vid, row.c_vid)}
                        </Tag>
                      ),
                    },
                    {
                      title: "限速带宽",
                      width: 96,
                      render: (_: unknown, row) =>
                        formatBandwidth(row.rate_limit_mbps ?? row.bandwidth_mbps),
                    },
                    {
                      title: "VNI",
                      dataIndex: "vni",
                      width: 80,
                      render: (v?: number) => (v != null ? v : "—"),
                    },
                    {
                      title: "VSI",
                      dataIndex: "vsi_name",
                      width: 160,
                      ellipsis: true,
                      render: (v?: string) => v || "—",
                    },
                    {
                      title: "描述",
                      dataIndex: "description",
                      width: 180,
                      ellipsis: true,
                      render: (v?: string) => v || "—",
                    },
                    {
                      title: "来源",
                      dataIndex: "source",
                      width: 88,
                      render: (source: string, row) => {
                        const meta =
                          BINDING_SOURCE[source] ||
                          (row.binding_type === "platform"
                            ? BINDING_SOURCE.platform
                            : BINDING_SOURCE.device);
                        return <Tag color={meta.color}>{meta.label}</Tag>;
                      },
                    },
                    {
                      title: "操作",
                      width: 88,
                      fixed: "right",
                      render: (_: unknown, row: DevicePortBinding) =>
                        row.binding_type === "device" && !row.circuit_id ? (
                          <Button type="link" size="small" onClick={() => setAdoptBinding(row)}>
                            纳管
                          </Button>
                        ) : row.circuit_id ? (
                          <Link to={`/circuits?circuit=${row.circuit_id}`}>查看</Link>
                        ) : (
                          "—"
                        ),
                    },
                  ]}
                />

                {bindings && bindings.unbound_interfaces.length > 0 ? (
                  <div style={{ marginTop: 16 }}>
                    <Typography.Text type="secondary">
                      空闲接口（可分配给新客户）：
                    </Typography.Text>
                    <div style={{ marginTop: 8 }}>
                      <Space size={[4, 4]} wrap>
                        {bindings.unbound_interfaces.slice(0, 40).map((name) => {
                          const short = formatInterfaceShort(name);
                          if (short === name) {
                            return <Tag key={name}>{short}</Tag>;
                          }
                          return (
                            <Tooltip key={name} title={formatInterfaceTooltip(name)}>
                              <Tag>{short}</Tag>
                            </Tooltip>
                          );
                        })}
                        {bindings.unbound_interfaces.length > 40 ? (
                          <Tag>+{bindings.unbound_interfaces.length - 40} 更多</Tag>
                        ) : null}
                      </Space>
                    </div>
                  </div>
                ) : null}
              </>
            ),
          },
        ]}
      />
      {device ? (
        <AdoptBindingModal
          open={!!adoptBinding}
          binding={adoptBinding}
          deviceId={device.id}
          onClose={() => setAdoptBinding(null)}
          onSuccess={() => loadBindings(device.id, true)}
        />
      ) : null}
    </Drawer>
  );
}

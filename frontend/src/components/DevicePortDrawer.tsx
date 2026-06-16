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
  DevicePortBindings,
  SvidUsage,
} from "../api/types";
import SvidUsageCell from "./SvidUsageCell";

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
  if (accessMode === "access") return "untagged";
  if (cVid != null && sVid != null) return `S:${sVid} / C:${cVid}`;
  if (sVid != null) return `S:${sVid}`;
  return "—";
}

function formatPortSpeed(mbps?: number) {
  if (!mbps) return "—";
  return mbps >= 1000 ? `${mbps / 1000}G` : `${mbps}M`;
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

  async function loadBindings(deviceId: number) {
    setBindingsLoading(true);
    try {
      const { data } = await api.get<DevicePortBindings>(`/devices/${deviceId}/port-bindings`);
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
        loadBindings(device.id),
      ]);
      if (cancelled || !rows) return;
      if (refreshVersion === 0 && rows.length === 0) {
        try {
          const discovered = await onDiscover(device.id);
          if (!cancelled && Array.isArray(discovered)) {
            setIfaces(discovered);
          }
        } catch {
          // discover errors are surfaced by parent handler
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
      loadBindings(device.id),
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
              onClick={async () => {
                const data = await onDiscover(device.id);
                if (Array.isArray(data)) setIfaces(data);
                await loadBindings(device.id);
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
                  loading={ifacesLoading}
                  dataSource={ifaceRows}
                  locale={{
                    emptyText: ifaceSvidOnly
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
                      width: 220,
                      fixed: "left",
                      render: (name: string) => (
                        <Typography.Text code copyable={{ text: name }}>
                          {name}
                        </Typography.Text>
                      ),
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
                        <Tag color={s === "up" ? "green" : "default"}>{s || "—"}</Tag>
                      ),
                    },
                    {
                      title: "ifIndex",
                      dataIndex: "ifindex",
                      width: 72,
                      render: (v?: number) => (v != null ? v : "—"),
                    },
                    {
                      title: "来源",
                      dataIndex: "discovered_via",
                      width: 88,
                      render: (d?: string) => (d ? <Tag>{d}</Tag> : "—"),
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
            label: `客户接入绑定 (${bindings?.total_bindings ?? 0})`,
            children: (
              <>
                <Alert
                  type="info"
                  showIcon
                  message="客户与接口的关联关系"
                  description="平台纳管：专线端点已绑定客户与物理口；现网占用：设备 running-config 中存在但尚未在平台创建专线的 VLAN。"
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

                <Table
                  rowKey={(row) =>
                    `${row.interface_name}-${row.binding_type}-${row.s_vid ?? "u"}-${row.c_vid ?? ""}-${row.circuit_id ?? row.source}`
                  }
                  size="small"
                  loading={bindingsLoading}
                  dataSource={bindings?.items ?? []}
                  locale={{ emptyText: "暂无客户接入绑定 · 可在专线编排中为该设备配置端点" }}
                  pagination={{
                    defaultPageSize: 50,
                    showSizeChanger: true,
                    pageSizeOptions: ["20", "50", "100"],
                    showTotal: (total) => `共 ${total} 条绑定`,
                  }}
                  scroll={{ x: 1180, y: "calc(100vh - 360px)" }}
                  columns={[
                    {
                      title: "接口",
                      dataIndex: "interface_name",
                      width: 200,
                      fixed: "left",
                      render: (name: string) => (
                        <Typography.Text code copyable={{ text: name }}>
                          {name}
                        </Typography.Text>
                      ),
                    },
                    {
                      title: "客户",
                      width: 180,
                      render: (_: unknown, row) =>
                        row.tenant_id ? (
                          <Link to={`/circuits?tenant=${row.tenant_id}`}>
                            {row.tenant_name}
                            <Typography.Text type="secondary"> ({row.tenant_code})</Typography.Text>
                          </Link>
                        ) : (
                          <Typography.Text type="secondary">未纳管</Typography.Text>
                        ),
                    },
                    {
                      title: "专线",
                      width: 200,
                      render: (_: unknown, row) =>
                        row.circuit_id ? (
                          <Space direction="vertical" size={0}>
                            <Typography.Text>{row.circuit_name}</Typography.Text>
                            <Typography.Text type="secondary" code>
                              {row.circuit_code}
                            </Typography.Text>
                          </Space>
                        ) : row.circuit_code ? (
                          <Typography.Text code>{row.circuit_code}</Typography.Text>
                        ) : (
                          "—"
                        ),
                    },
                    {
                      title: "端点",
                      dataIndex: "endpoint_label",
                      width: 64,
                      render: (v?: string) => v || "—",
                    },
                    {
                      title: "封装 / VLAN",
                      width: 140,
                      render: (_: unknown, row) =>
                        formatVlan(row.access_mode, row.s_vid, row.c_vid),
                    },
                    {
                      title: "VNI",
                      dataIndex: "vni",
                      width: 72,
                      render: (v?: number) => (v != null ? v : "—"),
                    },
                    {
                      title: "带宽",
                      dataIndex: "bandwidth_mbps",
                      width: 80,
                      render: (v?: number) => (v != null ? `${v}M` : "—"),
                    },
                    {
                      title: "专线状态",
                      dataIndex: "circuit_status",
                      width: 96,
                      render: (s?: string) =>
                        s ? <Tag color={CIRCUIT_STATUS_COLOR[s] || "default"}>{s}</Tag> : "—",
                    },
                    {
                      title: "来源",
                      dataIndex: "source",
                      width: 96,
                      render: (source: string, row) => {
                        const meta =
                          BINDING_SOURCE[source] ||
                          (row.binding_type === "platform"
                            ? BINDING_SOURCE.platform
                            : BINDING_SOURCE.device);
                        return <Tag color={meta.color}>{meta.label}</Tag>;
                      },
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
                        {bindings.unbound_interfaces.slice(0, 40).map((name) => (
                          <Tag key={name}>{name}</Tag>
                        ))}
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
    </Drawer>
  );
}

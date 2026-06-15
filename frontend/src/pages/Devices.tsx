import {
  ApiOutlined,
  BookOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  MoreOutlined,
  NodeIndexOutlined,
  PlusOutlined,
  RadarChartOutlined,
  RocketOutlined,
  SearchOutlined,
  SettingOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Col,
  Drawer,
  Dropdown,
  Input,
  Modal,
  Row,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type {
  Device,
  DeviceInterface,
  ManagementDefaults,
  Paginated,
  Site,
  SnmpDefaults,
  SvidUsage,
} from "../api/types";
import { ConfigPreviewPre } from "../utils/configPreview";
import {
  DEVICE_ROLE_OPTIONS,
  labelForOption,
} from "../constants/formOptions";
import { page as pageCopy, toast as toastCopy } from "../constants/uiCopy";
import { buildListQuery, dataTableProps, tablePagination } from "../utils/table";
import { PageCard } from "@/components";
import ListToolbar from "../components/ListToolbar";
import DeviceFormDialog, { type DeviceFormValues } from "@/components/DeviceFormDialog";
import SvidUsageCell from "@/components/SvidUsageCell";

const VENDOR_SHORT: Record<string, string> = {
  h3c: "H3C",
  huawei: "Huawei",
  juniper: "Juniper",
  arista: "Arista",
  cisco: "Cisco",
  frr: "FRR",
};

const DEVICE_STATUS_COLOR: Record<string, string> = {
  online: "green",
  offline: "red",
  maintenance: "orange",
  unknown: "default",
};

const DEVICE_STATUS_LABEL: Record<string, string> = {
  online: "在线",
  offline: "离线",
  maintenance: "维护",
  unknown: "未知",
};

const FALLBACK_SNMP: SnmpDefaults = {
  enabled: true,
  port: 161,
  community: "bugis-ro",
  version: "2c",
};

const FALLBACK_MGMT: ManagementDefaults = {
  netconf_port: 830,
  ssh_port: 22,
  username: "admin",
  management_transport: "auto",
  netconf_timeout: 30,
  ssh_timeout: 30,
  snmp: FALLBACK_SNMP,
};

function buildDevicePayload(
  values: DeviceFormValues,
  snmpDefaults: SnmpDefaults,
  editing?: Device | null,
): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...values };
  if (editing) delete payload.vendor;
  if (!payload.password) delete payload.password;
  if (!payload.enable_password) delete payload.enable_password;
  if (!payload.snmp_enabled) {
    payload.snmp_community = null;
  } else if (!payload.snmp_community) {
    delete payload.snmp_community;
  } else if (payload.snmp_community === snmpDefaults.community && !editing?.snmp_community_set) {
    delete payload.snmp_community;
  }
  if (!payload.snmp_v3_auth_password) delete payload.snmp_v3_auth_password;
  if (!payload.snmp_v3_priv_password) delete payload.snmp_v3_priv_password;
  if (payload.netmiko_device_type === "") payload.netmiko_device_type = null;
  if (payload.model === "") payload.model = null;
  if (payload.loopback_ip === "") payload.loopback_ip = null;
  if (payload.username === "") payload.username = null;
  if (payload.snmp_v3_username === "") payload.snmp_v3_username = null;
  return payload;
}

export default function Devices() {
  const { message, modal } = AntApp.useApp();
  const [rows, setRows] = useState<Device[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [search, setSearch] = useState("");
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [formDevice, setFormDevice] = useState<Device | null>(null);
  const [snmpDefaults, setSnmpDefaults] = useState<SnmpDefaults>(FALLBACK_SNMP);
  const [mgmtDefaults, setMgmtDefaults] = useState<ManagementDefaults>(FALLBACK_MGMT);
  const [learnOnImport, setLearnOnImport] = useState(true);
  const [drawerDevice, setDrawerDevice] = useState<Device | null>(null);
  const [ifaces, setIfaces] = useState<DeviceInterface[]>([]);
  const [ifacesLoading, setIfacesLoading] = useState(false);
  const [ifaceSvidOnly, setIfaceSvidOnly] = useState(false);
  const [initOpen, setInitOpen] = useState(false);
  const [initDevice, setInitDevice] = useState<Device | null>(null);
  const [initBaseline, setInitBaseline] = useState("");
  const [initLoading, setInitLoading] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  const siteName = useCallback((id?: number) => sites.find((s) => s.id === id)?.code || "-", [sites]);

  async function loadIfaces(deviceId: number, refresh = false) {
    setIfacesLoading(true);
    try {
      const { data } = await api.get<DeviceInterface[]>(`/devices/${deviceId}/interfaces`, {
        params: refresh ? { scan: true } : undefined,
      });
      setIfaces(data);
    } finally {
      setIfacesLoading(false);
    }
  }

  async function openPorts(device: Device) {
    setDrawerDevice(device);
    setIfaces([]);
    setIfaceSvidOnly(false);
    await loadIfaces(device.id, true);
  }

  async function load(p = page, ps = pageSize, q = search) {
    setLoading(true);
    try {
      const [d, s] = await Promise.all([
        api.get<Paginated<Device>>(`/devices${buildListQuery({ page: p, page_size: ps, q: q || undefined })}`),
        api.get<Site[]>("/sites"),
      ]);
      setRows(d.data.items);
      setTotal(d.data.total);
      setSites(s.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, pageSize]);

  async function ensureMgmtDefaults() {
    try {
      const { data } = await api.get<ManagementDefaults>("/system/management-defaults");
      setMgmtDefaults(data);
      setSnmpDefaults(data.snmp);
      return data;
    } catch {
      setMgmtDefaults(FALLBACK_MGMT);
      setSnmpDefaults(FALLBACK_SNMP);
      return FALLBACK_MGMT;
    }
  }

  async function openCreateModal() {
    await ensureMgmtDefaults();
    setFormMode("create");
    setFormDevice(null);
    setFormOpen(true);
  }

  async function openEditModal(device: Device) {
    await ensureMgmtDefaults();
    setFormMode("edit");
    setFormDevice(device);
    setFormOpen(true);
  }

  async function onFormSubmit(values: DeviceFormValues) {
    if (formMode === "edit" && formDevice) {
      try {
        const payload = buildDevicePayload(values, snmpDefaults, formDevice);
        payload.snmp_v3_auth_protocol = formDevice.snmp_v3_auth_protocol || "SHA";
        payload.snmp_v3_priv_protocol = formDevice.snmp_v3_priv_protocol || "AES";
        await api.patch(`/devices/${formDevice.id}`, payload);
        message.success(toastCopy.saved);
        setFormOpen(false);
        setFormDevice(null);
        load();
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } } };
        message.error(err?.response?.data?.detail || toastCopy.failed);
      }
      return;
    }

    try {
      await api.post("/devices", buildDevicePayload(values, snmpDefaults));
      message.success("设备已纳管");
      setFormOpen(false);
      setPage(1);
      load(1);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function remove(id: number) {
    await api.delete(`/devices/${id}`);
    message.success(toastCopy.deleted);
    load();
  }

  async function exportCsv() {
    const { data } = await api.get("/bulk/devices/export", { responseType: "text" });
    const blob = new Blob([data], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "devices.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function importCsv(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/bulk/devices/import", fd, {
        params: { learn: learnOnImport },
      });
      const learnMsg =
        data.learn_enabled && data.learn
          ? ` · 现网学习 ${data.learn.success}/${data.learn.total} 成功`
          : "";
      message.success(`导入完成 · 新增 ${data.created} · 跳过 ${data.skipped}${learnMsg}`);
      if (data.errors?.length) message.warning(`${data.errors.length} 行需修正`);
      setPage(1);
      load(1);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function discover(deviceId: number) {
    const hide = message.loading("SNMP 接口扫描中…", 0);
    try {
      const { data } = await api.post<DeviceInterface[]>(`/devices/${deviceId}/discover-interfaces`);
      hide();
      const simCount = data.filter((i) => i.discovered_via === "snmp-sim").length;
      const svidCount = data.filter((i) => i.used_s_vids?.length).length;
      if (simCount === data.length) {
        message.warning(
          "返回的是模拟数据（设备 SNMP 不可达或 Community 错误）。请检查管理 IP、UDP 161 与 Community 后重试",
        );
      } else if (simCount > 0) {
        message.warning(`部分接口为模拟数据（${simCount}/${data.length}），请检查 SNMP 配置`);
      } else {
        message.success(`SNMP 发现 ${data.length} 个接口 · ${svidCount} 个端口有 S-VID 占用`);
      }
      if (svidCount === 0 && simCount < data.length) {
        message.info("S-VID 需从 running-config 解析，请执行「现网学习」后重新检测");
      }
      setIfaces(data);
    } catch (e: unknown) {
      hide();
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function learnConfig(d: Device) {
    const hide = message.loading(`现网配置学习中 · ${d.name}...`, 0);
    try {
      const { data } = await api.post(`/devices/${d.id}/learn`);
      hide();
      if (data.success) {
        const inv = data.inventory;
        message.success(
          `${d.name} 学习完成 · ${inv?.service_count ?? 0} 个业务 · v${data.snapshot_version}`,
        );
        if (data.svid_scan?.ports_scanned || drawerDevice?.id === d.id) {
          await loadIfaces(d.id, true);
        }
      } else {
        message.error(data.error || toastCopy.failed);
      }
      load();
    } catch (e: unknown) {
      hide();
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function initialize(d: Device) {
    try {
      const { data: bl } = await api.get<{ content: string }>(`/devices/${d.id}/baseline`);
      setInitDevice(d);
      setInitBaseline(bl.content);
      setInitOpen(true);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function confirmInitialize() {
    if (!initDevice) return;
    setInitLoading(true);
    try {
      const { data } = await api.post(`/devices/${initDevice.id}/initialize`);
      message.success(`${data.device} 初始化完成 · v${data.version} · ${data.transport}`);
      setInitOpen(false);
      setInitDevice(null);
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    } finally {
      setInitLoading(false);
    }
  }

  async function check(id: number) {
    const hide = message.loading("可达性探测 · S-VID 扫描中…", 0);
    try {
      const { data } = await api.post(`/devices/${id}/check`);
      hide();
      if (data.reachable) {
        const scan = data.svid_scan;
        const svidCount = scan?.total_s_vids ?? 0;
        const conflictCount = scan?.conflicts?.length ?? 0;
        if (conflictCount > 0) {
          message.warning(
            `${data.device} 可达 · 发现 ${svidCount} 个 S-VID · ${conflictCount} 处冲突`,
          );
        } else {
          message.success(
            `${data.device} 可达 (${data.latency_ms}ms) · 已扫描 ${svidCount} 个 S-VID 占用`,
          );
        }
        if (drawerDevice?.id === id && scan?.ports?.length) {
          const ports = scan.ports as Array<{
            interface: string;
            s_vids: SvidUsage[];
            allocated: boolean;
          }>;
          const byName = Object.fromEntries(ports.map((row) => [row.interface, row]));
          setIfaces((existing) => {
            const merged = existing.map((iface) => {
              const hit = byName[iface.name];
              if (!hit) return iface;
              return { ...iface, used_s_vids: hit.s_vids, allocated: hit.allocated };
            });
            for (const row of ports) {
              if (!merged.some((i) => i.name === row.interface)) {
                merged.push({
                  id: -1,
                  device_id: id,
                  name: row.interface,
                  admin_up: true,
                  allocated: row.allocated,
                  used_s_vids: row.s_vids,
                } as DeviceInterface);
              }
            }
            return merged;
          });
        }
      } else {
        message.error(`${data.device} 不可达 (${data.mgmt_ip})`);
      }
      load();
    } catch (e: unknown) {
      hide();
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  const ifaceHasSvid = ifaces.some((i) => (i.used_s_vids?.length ?? 0) > 0);

  const ifaceRows = useMemo(
    () => (ifaceSvidOnly ? ifaces.filter((i) => (i.used_s_vids?.length ?? 0) > 0) : ifaces),
    [ifaces, ifaceSvidOnly],
  );

  const ifaceSvidTotal = useMemo(
    () => ifaces.reduce((sum, i) => sum + (i.used_s_vids?.length ?? 0), 0),
    [ifaces],
  );

  const stats = useMemo(() => {
    const online = rows.filter((r) => r.status === "online").length;
    const offline = rows.filter((r) => r.status === "offline").length;
    return { online, offline };
  }, [rows]);

  function runSearch() {
    setPage(1);
    load(1, pageSize, search);
  }

  return (
    <PageCard
      title={pageCopy.devices}
      description="多厂商 Fabric 纳管 · SNMP / NETCONF / SSH"
      extra={
        <Space wrap size={8}>
          <Dropdown
            menu={{
              items: [
                { key: "mgmt", label: <Link to="/settings/management">南向接口</Link> },
                { key: "snmp", label: <Link to="/settings/snmp">SNMP 采集</Link> },
              ],
            }}
          >
            <Button icon={<SettingOutlined />}>设置</Button>
          </Dropdown>
          <Button icon={<DownloadOutlined />} onClick={exportCsv}>
            导出
          </Button>
          <input
            ref={importRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void importCsv(file);
              e.target.value = "";
            }}
          />
          <Button icon={<UploadOutlined />} onClick={() => importRef.current?.click()}>
            导入
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
            纳管设备
          </Button>
        </Space>
      }
    >
      <ListToolbar
        summary={`共 ${total.toLocaleString()} 台 · ${stats.online} 在线 · ${stats.offline} 离线`}
        left={
          <Input.Search
            allowClear
            placeholder="搜索名称或管理 IP"
            style={{ width: 280 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onSearch={runSearch}
            enterButton={<SearchOutlined />}
          />
        }
        right={
          <Space size={6}>
            <Typography.Text type="secondary">导入即学习</Typography.Text>
            <Switch checked={learnOnImport} onChange={setLearnOnImport} size="small" />
          </Space>
        }
      />

      <Row gutter={[12, 12]} style={{ marginBottom: 16, maxWidth: 720 }}>
        <Col xs={24} sm={8}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic title="设备总数" value={total} suffix="台" />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic title="在线" value={stats.online} valueStyle={{ color: "#3f8600" }} suffix="台" />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic
              title="离线"
              value={stats.offline}
              valueStyle={{ color: stats.offline ? "#cf1322" : "#8c8c8c" }}
              suffix="台"
            />
          </Card>
        </Col>
      </Row>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        locale={{ emptyText: "暂无设备 · 从导入或纳管开始" }}
        {...dataTableProps(1040, true)}
        pagination={tablePagination(total, page, pageSize, (p, ps) => {
          setPage(p);
          setPageSize(ps);
        })}
        columns={[
          {
            title: "设备",
            dataIndex: "name",
            width: 200,
            ellipsis: true,
            render: (name: string, d: Device) => (
              <Tooltip
                title={
                  [d.hostname, d.loopback_ip && `Loopback ${d.loopback_ip}`, d.bgp_asn && `AS ${d.bgp_asn}`]
                    .filter(Boolean)
                    .join(" · ") || name
                }
              >
                <div style={{ minWidth: 0 }}>
                  <Button type="link" size="small" style={{ padding: 0, height: "auto" }} onClick={() => openEditModal(d)}>
                    <span style={{ fontWeight: 500 }}>{name}</span>
                  </Button>
                  {d.model ? (
                    <Typography.Text type="secondary" ellipsis style={{ fontSize: 12, display: "block" }}>
                      {d.model}
                    </Typography.Text>
                  ) : null}
                </div>
              </Tooltip>
            ),
          },
          {
            title: "厂商",
            dataIndex: "vendor",
            width: 88,
            render: (v: string) => <Tag>{VENDOR_SHORT[v] || v}</Tag>,
          },
          {
            title: "角色",
            dataIndex: "role",
            width: 64,
            render: (r: string) => labelForOption(DEVICE_ROLE_OPTIONS, r).split(" ")[0],
          },
          {
            title: "管理 IP",
            dataIndex: "mgmt_ip",
            width: 140,
            ellipsis: true,
            render: (ip: string) => <Typography.Text code>{ip}</Typography.Text>,
          },
          {
            title: "站点",
            width: 96,
            ellipsis: true,
            render: (_: unknown, r: Device) => siteName(r.site_id),
          },
          {
            title: "凭证",
            width: 52,
            align: "center" as const,
            render: (_: unknown, r: Device) =>
              r.password_set || r.username ? (
                <CheckCircleOutlined style={{ color: "#52c41a", fontSize: 16 }} />
              ) : (
                <CloseCircleOutlined style={{ color: "#d9d9d9", fontSize: 16 }} />
              ),
          },
          {
            title: "SNMP",
            width: 68,
            render: (_: unknown, r: Device) =>
              r.snmp_enabled === false ? (
                <Typography.Text type="secondary">—</Typography.Text>
              ) : (
                <Tag color="geekblue">v{r.snmp_version || "2c"}</Tag>
              ),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 76,
            render: (s: string) => (
              <Tag color={DEVICE_STATUS_COLOR[s] || "default"}>{DEVICE_STATUS_LABEL[s] || s}</Tag>
            ),
          },
          {
            title: "操作",
            key: "actions",
            width: 196,
            fixed: "right" as const,
            className: "table-actions",
            render: (_: unknown, r: Device) => (
              <Space size={4} wrap={false} className="table-actions">
                <Button size="small" type="primary" icon={<ApiOutlined />} onClick={() => openPorts(r)}>
                  端口
                </Button>
                <Tooltip title="编辑设备信息">
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(r)} />
                </Tooltip>
                <Dropdown
                  trigger={["click"]}
                  menu={{
                    items: [
                      {
                        key: "edit",
                        icon: <EditOutlined />,
                        label: "编辑设备",
                        onClick: () => openEditModal(r),
                      },
                      { type: "divider" },
                      {
                        key: "learn",
                        icon: <BookOutlined />,
                        label: "现网学习",
                        onClick: () => learnConfig(r),
                      },
                      {
                        key: "init",
                        icon: <RocketOutlined />,
                        label: "初始化",
                        onClick: () => initialize(r),
                      },
                      {
                        key: "check",
                        icon: <RadarChartOutlined />,
                        label: "检测",
                        onClick: () => check(r.id),
                      },
                      {
                        key: "discover",
                        icon: <NodeIndexOutlined />,
                        label: "SNMP 发现",
                        onClick: () => discover(r.id),
                      },
                      { type: "divider" },
                      {
                        key: "delete",
                        icon: <DeleteOutlined />,
                        label: "删除",
                        danger: true,
                        onClick: () =>
                          modal.confirm({
                            title: "确认删除该设备?",
                            content: "此操作不可撤销，将永久删除该设备及其关联数据。",
                            okType: "danger",
                            okText: "删除",
                            onOk: () => remove(r.id),
                          }),
                      },
                    ],
                  }}
                >
                  <Button size="small" icon={<MoreOutlined />} />
                </Dropdown>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={drawerDevice ? `端口清单 · ${drawerDevice.name}` : "端口清单"}
        width="min(96vw, 1280px)"
        open={!!drawerDevice}
        onClose={() => setDrawerDevice(null)}
        destroyOnClose
        extra={
          drawerDevice ? (
            <Space wrap>
              <Button size="small" icon={<RadarChartOutlined />} onClick={() => check(drawerDevice.id)}>
                检测 S-VID
              </Button>
              <Button size="small" icon={<NodeIndexOutlined />} onClick={() => discover(drawerDevice.id)}>
                SNMP 发现
              </Button>
              <Button size="small" icon={<BookOutlined />} onClick={() => learnConfig(drawerDevice)}>
                现网学习
              </Button>
              <Button size="small" type="link" onClick={() => loadIfaces(drawerDevice.id, true)}>
                刷新占用
              </Button>
            </Space>
          ) : null
        }
      >
        <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
          IF-MIB 端口与 S-VID 占用 · SNMP 发现接口，现网学习或检测刷新 VLAN 占用
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

        {!ifacesLoading && ifaces.length > 0 && !ifaceHasSvid ? (
          <Alert
            type="info"
            showIcon
            message="暂无 S-VID 占用数据"
            description="S-VID 从 running-config（service-instance / dot1q 等）解析，SNMP 仅提供端口清单。请先执行「现网学习」拉取配置，再点「检测 S-VID」或「刷新占用」。"
            style={{ marginBottom: 12 }}
          />
        ) : null}

        {ifaceHasSvid ? (
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <Typography.Text type="secondary">
              全设备共 {ifaceSvidTotal.toLocaleString()} 个 S-VID 占用 · {ifaces.length.toLocaleString()} 个端口
            </Typography.Text>
            <Space size={6}>
              <Typography.Text type="secondary">仅显示有占用</Typography.Text>
              <Switch checked={ifaceSvidOnly} onChange={setIfaceSvidOnly} size="small" />
            </Space>
          </div>
        ) : null}

        <Table
          rowKey={(r) => `${r.device_id}-${r.name}`}
          size="small"
          loading={ifacesLoading}
          dataSource={ifaceRows}
          locale={{ emptyText: ifaceSvidOnly ? "暂无 S-VID 占用端口" : "暂无端口数据 · 先执行 SNMP 发现" }}
          pagination={{ pageSize: 20, showSizeChanger: true, pageSizeOptions: ["20", "50", "100"] }}
          scroll={{ x: 880 }}
          columns={[
            {
              title: "接口",
              dataIndex: "name",
              width: 160,
              ellipsis: true,
              render: (name: string) => (
                <Tooltip title={name}>
                  <Typography.Text code ellipsis style={{ maxWidth: 140 }}>
                    {name}
                  </Typography.Text>
                </Tooltip>
              ),
            },
            {
              title: "描述",
              dataIndex: "description",
              width: 220,
              ellipsis: true,
              render: (d?: string) =>
                d ? (
                  <Tooltip title={d}>
                    <Typography.Text type="secondary" ellipsis style={{ maxWidth: 200 }}>
                      {d}
                    </Typography.Text>
                  </Tooltip>
                ) : (
                  "—"
                ),
            },
            {
              title: "速率",
              dataIndex: "speed_mbps",
              width: 72,
              render: (s?: number) => {
                if (!s) return "—";
                return <Tag>{s >= 1000 ? `${s / 1000}G` : `${s}M`}</Tag>;
              },
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
              width: 140,
              render: (list?: SvidUsage[]) => <SvidUsageCell list={list} />,
            },
          ]}
        />
      </Drawer>

      <DeviceFormDialog
        open={formOpen}
        onOpenChange={(o) => {
          setFormOpen(o);
          if (!o) setFormDevice(null);
        }}
        mode={formMode}
        device={formDevice}
        sites={sites}
        mgmtDefaults={mgmtDefaults}
        snmpDefaults={snmpDefaults}
        onSubmit={onFormSubmit}
      />

      <Modal
        title={initDevice ? `基线初始化 · ${initDevice.name} (${initDevice.vendor})` : "基线初始化"}
        open={initOpen}
        onCancel={() => !initLoading && setInitOpen(false)}
        onOk={confirmInitialize}
        okText={initLoading ? "下发中…" : "下发基线配置"}
        confirmLoading={initLoading}
        width={960}
        destroyOnClose
      >
        <Typography.Paragraph type="secondary">
          标准基线预览（管理 / Loopback / Underlay / EVPN Overlay）· 确认后 dry-run 下发并归档初始化快照
        </Typography.Paragraph>
        <ConfigPreviewPre>{initBaseline}</ConfigPreviewPre>
      </Modal>
    </PageCard>
  );
}

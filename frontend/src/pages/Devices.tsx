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
} from "../api/types";
import { ConfigPreviewPre } from "../utils/configPreview";
import {
  DEVICE_ROLE_OPTIONS,
  labelForOption,
  mgmtIpTypeLabel,
} from "../constants/formOptions";
import { page as pageCopy, toast as toastCopy } from "../constants/uiCopy";
import { buildListQuery, dataTableProps, TABLE_SCROLL, tablePagination, withMobileHide } from "../utils/table";
import { PageCard } from "@/components";
import ListToolbar from "../components/ListToolbar";
import DeviceFormDialog, { type DeviceFormValues } from "@/components/DeviceFormDialog";
import DevicePortDrawer from "@/components/DevicePortDrawer";
import { useInterfaceDescJobs } from "@/hooks/useInterfaceDescJobs";
import { useTc } from "@/i18n/useTc";
import { useTranslation } from "react-i18next";
import { deviceStatusLabel } from "../i18n/helpers";

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
  const { tc } = useTc();
  const { t } = useTranslation();
  const { message, modal } = AntApp.useApp();
  const descJobs = useInterfaceDescJobs(message);
  const [rows, setRows] = useState<Device[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState({ total: 0, online: 0, offline: 0 });
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
  const [portDrawerRefresh, setPortDrawerRefresh] = useState(0);
  const [initOpen, setInitOpen] = useState(false);
  const [initDevice, setInitDevice] = useState<Device | null>(null);
  const [initBaseline, setInitBaseline] = useState("");
  const [initLoading, setInitLoading] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  const siteName = useCallback((id?: number) => sites.find((s) => s.id === id)?.code || "-", [sites]);

  function openPorts(device: Device) {
    setDrawerDevice(device);
  }

  function bumpPortDrawer() {
    setPortDrawerRefresh((v) => v + 1);
  }

  async function load(p = page, ps = pageSize, q = search) {
    setLoading(true);
    try {
      const [d, s, sum] = await Promise.all([
        api.get<Paginated<Device>>(`/devices${buildListQuery({ page: p, page_size: ps, q: q || undefined })}`),
        api.get<Site[]>("/sites"),
        api.get<{ total: number; online: number; offline: number }>("/devices/summary"),
      ]);
      setRows(d.data.items);
      setTotal(d.data.total);
      setSites(s.data);
      setSummary(sum.data);
    } catch {
      message.error(toastCopy.failed);
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
      message.success(tc('设备已纳管'));
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
      const cfgCount = data.filter((i) => i.discovered_via === "running-config").length;
      const svidCount = data.filter((i) => i.used_s_vids?.length).length;
      if (simCount === data.length) {
        message.warning(
          "返回的是模拟数据（设备 SNMP 不可达或 Community/端口错误）。华为请确认 UDP 16161 与管理网 IP 可达后重试",
        );
      } else if (cfgCount > 0 && !data.some((i) => i.discovered_via === "snmp")) {
        message.info(
          `SNMP 不可达，已从 running-config 解析 ${data.length} 个物理口（${svidCount} 个有 S-VID 占用）`,
        );
      } else if (simCount > 0) {
        message.warning(`部分接口为模拟数据（${simCount}/${data.length}），请检查 SNMP 配置`);
      } else {
        message.success(`SNMP 发现 ${data.length} 个接口 · ${svidCount} 个端口有 S-VID 占用`);
      }
      if (svidCount === 0 && simCount < data.length) {
        message.info(tc('S-VID 需从 running-config 解析，请执行「现网学习」后重新检测'));
      }
      bumpPortDrawer();
      return data;
    } catch (e: unknown) {
      hide();
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
      throw e;
    }
  }

  async function learnConfig(d: Device) {
    const hide = message.loading(`现网配置学习中 · ${d.name}...`, 0);
    try {
      const { data } = await api.post(`/devices/${d.id}/learn`);
      hide();
      if (data.success) {
        const inv = data.inventory;
        const svidTotal = data.svid_scan?.total_s_vids ?? 0;
        if (data.dry_run) {
          message.warning(`${d.name} 学习完成（Dry-run：未从真实设备拉取配置）`);
        } else {
          message.success(
            `${d.name} 学习完成 · ${inv?.service_count ?? 0} 个业务 · v${data.snapshot_version}`,
          );
        }
        if (svidTotal === 0) {
          message.info(tc('未解析到 S-VID，请确认设备 running-config 含 service-instance / dot1q 配置'));
        }
        bumpPortDrawer();
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
        const dryTag = data.dry_run ? " · 配置 dry-run" : "";
        const activeTag = data.mgmt_ip_active
          ? ` · 当前 ${data.mgmt_ip_active_label || data.mgmt_ip_active_role} ${data.mgmt_ip_active}`
          : "";
        if (conflictCount > 0) {
          message.warning(
            `${data.device} 可达 · 发现 ${svidCount} 个 S-VID · ${conflictCount} 处冲突`,
          );
        } else {
          message.success(
            `${data.device} 可达${data.method ? ` · ${data.method}` : ""} (${data.latency_ms}ms) · 已扫描 ${svidCount} 个 S-VID 占用${activeTag}${dryTag}`,
          );
        }
        bumpPortDrawer();
      } else {
        const tried = (data.probes as Array<{ method?: string }> | undefined)
          ?.map((p) => p.method)
          .filter(Boolean)
          .join(" / ");
        message.warning(
          `${data.device} 管理面不可达${data.mgmt_ip_backup ? `（主 ${data.mgmt_ip} / 备 ${data.mgmt_ip_backup}）` : ` (${data.mgmt_ip})`}${tried ? ` · 已探测 ${tried}` : ""} · 请检查 IP、端口、SNMP Community 与防火墙`,
          6,
        );
      }
      load();
    } catch (e: unknown) {
      hide();
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  const stats = useMemo(
    () => ({ online: summary.online, offline: summary.offline }),
    [summary],
  );

  function runSearch() {
    setPage(1);
    load(1, pageSize, search);
  }

  return (
    <PageCard
      title={pageCopy.devices}
      description={tc('多厂商 Fabric 纳管 · SNMP / NETCONF / SSH')}
      extra={
        <Space wrap size={8}>
          <Dropdown
            menu={{
              items: [
                { key: "mgmt", label: <Link to="/settings/management">{tc('南向接口')}</Link> },
                { key: "snmp", label: <Link to="/settings/snmp">{tc('SNMP 采集')}</Link> },
              ],
            }}
          >
            <Button icon={<SettingOutlined />}>{tc('设置')}</Button>
          </Dropdown>
          <Button icon={<DownloadOutlined />} onClick={exportCsv}>{tc('导出')}</Button>
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
          <Button icon={<UploadOutlined />} onClick={() => importRef.current?.click()}>{tc('导入')}</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>{tc('纳管设备')}</Button>
        </Space>
      }
    >
      <ListToolbar
        summary={t("devices.summary", {
          total: total.toLocaleString(),
          online: stats.online,
          offline: stats.offline,
        })}
        left={
          <Input.Search
            allowClear
            placeholder={tc('搜索名称或管理 IP')}
            style={{ width: 280 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onSearch={runSearch}
            enterButton={<SearchOutlined />}
          />
        }
        right={
          <Space size={6}>
            <Typography.Text type="secondary">{tc('导入即学习')}</Typography.Text>
            <Switch checked={learnOnImport} onChange={setLearnOnImport} size="small" />
          </Space>
        }
      />

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic title={tc('设备总数')} value={total} suffix={t("devices.unitSuffix")} />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic title={tc('在线')} value={stats.online} valueStyle={{ color: "#3f8600" }} suffix={t("devices.unitSuffix")} />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic
              title={tc('离线')}
              value={stats.offline}
              valueStyle={{ color: stats.offline ? "#cf1322" : "#8c8c8c" }}
              suffix={t("devices.unitSuffix")}
            />
          </Card>
        </Col>
      </Row>

      {descJobs.activeSaveCount > 0 ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${descJobs.activeSaveCount} 台设备接口描述正在后台下发，可继续编辑其他设备`}
        />
      ) : null}

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        locale={{ emptyText: tc("暂无设备 · 从导入或纳管开始") }}
        {...dataTableProps(TABLE_SCROLL.lg)}
        pagination={tablePagination(total, page, pageSize, (p, ps) => {
          setPage(p);
          setPageSize(ps);
        })}
        columns={withMobileHide(
          [
          {
            title: tc('设备'),
            dataIndex: "name",
            width: "22%",
            ellipsis: true,
            render: (name: string, d: Device) => {
              const job = descJobs.getJob(d.id);
              return (
              <Tooltip
                title={
                  [d.hostname, d.loopback_ip && `Loopback ${d.loopback_ip}`, d.bgp_asn && `AS ${d.bgp_asn}`]
                    .filter(Boolean)
                    .join(" · ") || name
                }
              >
                <div style={{ minWidth: 0 }}>
                  <Space size={6} wrap>
                    <Button type="link" size="small" style={{ padding: 0, height: "auto" }} onClick={() => openEditModal(d)}>
                      <span style={{ fontWeight: 500 }}>{name}</span>
                    </Button>
                    {job?.status === "saving" ? <Tag color="processing">下发中</Tag> : null}
                    {job?.status === "success" ? <Tag color="success">已下发</Tag> : null}
                    {job?.status === "error" ? <Tag color="error">下发失败</Tag> : null}
                  </Space>
                  {d.model ? (
                    <Typography.Text type="secondary" ellipsis style={{ fontSize: 12, display: "block" }}>
                      {d.model}
                    </Typography.Text>
                  ) : null}
                </div>
              </Tooltip>
            );
            },
          },
          {
            title: tc('厂商'),
            dataIndex: "vendor",
            width: "8%",
            render: (v: string) => <Tag>{VENDOR_SHORT[v] || v}</Tag>,
          },
          {
            title: tc('角色'),
            dataIndex: "role",
            width: "6%",
            render: (r: string) => labelForOption(DEVICE_ROLE_OPTIONS, r).split(" ")[0],
          },
          {
            title: tc('管理 IP'),
            dataIndex: "mgmt_ip",
            width: "18%",
            ellipsis: true,
            render: (_ip: string, d: Device) => {
              const primaryLabel = mgmtIpTypeLabel(d.mgmt_ip_primary_label);
              const backupLabel = mgmtIpTypeLabel(d.mgmt_ip_backup_label);
              const active = d.mgmt_ip_active;
              const activeRole = d.mgmt_ip_active_role;
              return (
                <div style={{ minWidth: 0 }}>
                  <div>
                    <Tag bordered={false} color={activeRole === "primary" ? "blue" : "default"} style={{ marginRight: 4 }}>
                      {primaryLabel}
                    </Tag>
                    <Typography.Text code={activeRole === "primary"}>{d.mgmt_ip}</Typography.Text>
                  </div>
                  {d.mgmt_ip_backup ? (
                    <div style={{ marginTop: 4 }}>
                      <Tag bordered={false} color={activeRole === "backup" ? "blue" : "default"} style={{ marginRight: 4 }}>
                        {backupLabel}
                      </Tag>
                      <Typography.Text code={activeRole === "backup"} type={activeRole === "backup" ? undefined : "secondary"}>
                        {d.mgmt_ip_backup}
                      </Typography.Text>
                    </div>
                  ) : null}
                  {active && activeRole ? (
                    <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 2 }}>
                      {t("devices.inUse", {
                        label: activeRole === "backup" ? backupLabel : primaryLabel,
                        ip: active,
                      })}
                    </Typography.Text>
                  ) : null}
                </div>
              );
            },
          },
          {
            title: tc('站点'),
            key: "site",
            width: "12%",
            ellipsis: true,
            render: (_: unknown, r: Device) => siteName(r.site_id),
          },
          {
            title: tc('凭证'),
            key: "credentials",
            width: "5%",
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
            key: "snmp",
            width: "7%",
            render: (_: unknown, r: Device) =>
              r.snmp_enabled === false ? (
                <Typography.Text type="secondary">—</Typography.Text>
              ) : (
                <Tag color="geekblue">v{r.snmp_version || "2c"}</Tag>
              ),
          },
          {
            title: tc('状态'),
            dataIndex: "status",
            width: "8%",
            render: (s: string) => (
              <Tag color={DEVICE_STATUS_COLOR[s] || "default"}>{deviceStatusLabel(t, s)}</Tag>
            ),
          },
          {
            title: tc('操作'),
            key: "actions",
            width: "18%",
            className: "table-actions",
            render: (_: unknown, r: Device) => (
                <Space size={4} className="table-actions">
                  <Button size="small" type="primary" icon={<ApiOutlined />} onClick={() => openPorts(r)}>{tc('端口')}</Button>
                <Tooltip title={tc('编辑设备信息')}>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(r)} />
                </Tooltip>
                <Dropdown
                  trigger={["click"]}
                  menu={{
                    items: [
                      {
                        key: "learn",
                        icon: <BookOutlined />,
                        label: tc('现网学习'),
                        onClick: () => learnConfig(r),
                      },
                      {
                        key: "init",
                        icon: <RocketOutlined />,
                        label: tc('初始化'),
                        onClick: () => initialize(r),
                      },
                      {
                        key: "check",
                        icon: <RadarChartOutlined />,
                        label: tc('检测'),
                        onClick: () => check(r.id),
                      },
                      {
                        key: "discover",
                        icon: <NodeIndexOutlined />,
                        label: tc('SNMP 发现'),
                        onClick: () => discover(r.id),
                      },
                      { type: "divider" },
                      {
                        key: "delete",
                        icon: <DeleteOutlined />,
                        label: tc('删除'),
                        danger: true,
                        onClick: () =>
                          modal.confirm({
                            title: tc('确认删除该设备?'),
                            content: "此操作不可撤销，将永久删除该设备及其关联数据。",
                            okType: "danger",
                            okText: tc('删除'),
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
        ],
          ["vendor", "role", "site", "credentials", "snmp"],
        )}
      />

      <DevicePortDrawer
        device={drawerDevice}
        refreshVersion={portDrawerRefresh}
        onClose={() => setDrawerDevice(null)}
        onCheck={check}
        onDiscover={discover}
        onLearn={learnConfig}
        editingDesc={drawerDevice ? descJobs.isEditing(drawerDevice.id) : false}
        descDraft={drawerDevice ? descJobs.getDraft(drawerDevice.id) : {}}
        saveJob={drawerDevice ? descJobs.getJob(drawerDevice.id) : null}
        onBeginEdit={(ports) => drawerDevice && descJobs.beginEdit(drawerDevice.id, ports)}
        onCancelEdit={() => drawerDevice && descJobs.cancelEdit(drawerDevice.id)}
        onDraftChange={(name, value) => drawerDevice && descJobs.updateDraft(drawerDevice.id, name, value)}
        onEnqueueSave={(ports, draft) =>
          drawerDevice &&
          descJobs.enqueueSave(drawerDevice, ports, draft, () => setPortDrawerRefresh((v) => v + 1))
        }
      />

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
        <Typography.Paragraph type="secondary">{tc('标准基线预览（管理 / Loopback / Underlay / EVPN Overlay）· 确认后 dry-run 下发并归档初始化快照')}</Typography.Paragraph>
        <ConfigPreviewPre>{initBaseline}</ConfigPreviewPre>
      </Modal>
    </PageCard>
  );
}

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
import { useDeviceCheckJobs } from "@/hooks/useDeviceCheckJobs";
import { useLearnJobs } from "@/hooks/useLearnJobs";
import { useSnmpDiscoverJobs } from "@/hooks/useSnmpDiscoverJobs";
import { fetchAllPages } from "@/utils/pagination";
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
  const learnJobs = useLearnJobs(message);
  const checkJobs = useDeviceCheckJobs(message);
  const snmpDiscoverJobs = useSnmpDiscoverJobs(message);
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
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchLearning, setBatchLearning] = useState(false);
  const [batchChecking, setBatchChecking] = useState(false);
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
      const payload = buildDevicePayload(values, snmpDefaults);
      const { data } = await api.post<Device & { learn_scheduled?: boolean }>(
        "/devices",
        payload,
      );
      setFormOpen(false);
      setFormDevice(null);
      setPage(1);
      load(1);
      if (data.learn_scheduled) {
        message.success(`${data.name} 已纳管 · 现网学习已在后台进行`);
        learnJobs.watchScheduledLearn(data.id, data.name, () => load());
      } else {
        message.success(tc("设备已纳管"));
      }
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
          ? data.learn.scheduled
            ? ` · 现网学习已在后台进行 (${data.learn.total} 台)`
            : ` · 现网学习 ${data.learn.success}/${data.learn.total} 成功`
          : "";
      message.success(`导入完成 · 新增 ${data.created} · 跳过 ${data.skipped}${learnMsg}`);
      if (data.learn_enabled && data.learn?.scheduled) {
        message.info(tc("导入设备的现网学习在后台并行执行，列表会显示「学习中」状态"));
      }
      if (data.errors?.length) message.warning(`${data.errors.length} 行需修正`);
      setPage(1);
      load(1);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || toastCopy.failed);
    }
  }

  async function discover(deviceId: number, deviceName?: string) {
    const device = rows.find((row) => row.id === deviceId);
    const name = deviceName ?? device?.name ?? `设备 ${deviceId}`;
    return snmpDiscoverJobs.discoverOne(deviceId, name, () => {
      bumpPortDrawer();
      load();
    });
  }

  function learnConfig(d: Device) {
    void learnJobs.learnOne(d, () => {
      bumpPortDrawer();
      load();
    });
  }

  async function learnSelected() {
    const selected = rows.filter((r) => selectedRowKeys.includes(r.id));
    if (!selected.length) {
      message.info(tc("请先勾选要学习的设备"));
      return;
    }
    setBatchLearning(true);
    try {
      await learnJobs.learnBatch(selected, () => {
        bumpPortDrawer();
        load();
      });
    } finally {
      setBatchLearning(false);
    }
  }

  async function learnAllOnline() {
    setBatchLearning(true);
    try {
      const all = await fetchAllPages<Device>("/devices", { page_size: 200 });
      const online = all.filter((d) => d.status === "online");
      if (!online.length) {
        message.info(tc("当前没有在线设备"));
        return;
      }
      await learnJobs.learnBatch(online, () => {
        bumpPortDrawer();
        load();
      });
    } finally {
      setBatchLearning(false);
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

  function checkDevice(d: Device) {
    checkJobs.checkOne(d, () => {
      bumpPortDrawer();
      load();
    });
  }

  function checkSelected() {
    const selected = rows.filter((r) => selectedRowKeys.includes(r.id));
    if (!selected.length) {
      message.info(tc("请先勾选要探测的设备"));
      return;
    }
    setBatchChecking(true);
    checkJobs.checkBatch(selected, () => {
      bumpPortDrawer();
      load();
    });
    setBatchChecking(false);
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

      {learnJobs.activeLearnCount > 0 ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${learnJobs.activeLearnCount} 台设备配置学习进行中（并行），可切换设备继续操作`}
        />
      ) : null}

      {checkJobs.activeCheckCount > 0 ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${checkJobs.activeCheckCount} 台设备可达性探测 / S-VID 扫描进行中（并行），可继续操作其他设备`}
        />
      ) : null}

      <Space wrap style={{ marginBottom: 12 }}>
        <Button
          icon={<RadarChartOutlined />}
          loading={batchChecking}
          disabled={selectedRowKeys.length === 0}
          onClick={() => void checkSelected()}
        >
          {tc("批量探测")}
          {selectedRowKeys.length > 0 ? ` (${selectedRowKeys.length})` : ""}
        </Button>
        <Button
          icon={<BookOutlined />}
          loading={batchLearning}
          disabled={selectedRowKeys.length === 0}
          onClick={() => void learnSelected()}
        >
          {tc("批量现网学习")}
          {selectedRowKeys.length > 0 ? ` (${selectedRowKeys.length})` : ""}
        </Button>
        <Button
          icon={<BookOutlined />}
          loading={batchLearning}
          onClick={() => void learnAllOnline()}
        >
          {tc("学习全部在线设备")}
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys),
        }}
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
              const learnJob = learnJobs.getJob(d.id);
              const checkJob = checkJobs.getJob(d.id);
              const snmpJob = snmpDiscoverJobs.getJob(d.id);
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
                    {learnJob?.status === "learning" ? <Tag color="processing">学习中</Tag> : null}
                    {learnJob?.status === "success" ? <Tag color="success">已学习</Tag> : null}
                    {learnJob?.status === "error" ? <Tag color="error">学习失败</Tag> : null}
                    {checkJob?.status === "checking" ? <Tag color="processing">探测中</Tag> : null}
                    {checkJob?.status === "success" ? <Tag color="success">已探测</Tag> : null}
                    {checkJob?.status === "error" ? <Tag color="error">探测失败</Tag> : null}
                    {snmpJob?.status === "discovering" ? <Tag color="processing">SNMP 扫描中</Tag> : null}
                    {snmpJob?.status === "success" ? <Tag color="success">已扫描</Tag> : null}
                    {snmpJob?.status === "error" ? <Tag color="error">扫描失败</Tag> : null}
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
                        onClick: () => checkDevice(r),
                      },
                      {
                        key: "discover",
                        icon: <NodeIndexOutlined />,
                        label: tc('SNMP 发现'),
                        onClick: () => discover(r.id, r.name),
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
        onCheck={checkDevice}
        checkJob={drawerDevice ? checkJobs.getJob(drawerDevice.id) : null}
        snmpDiscoverJob={drawerDevice ? snmpDiscoverJobs.getJob(drawerDevice.id) : null}
        onDiscover={discover}
        onLearn={learnConfig}
        editingDesc={drawerDevice ? descJobs.isEditing(drawerDevice.id) : false}
        descDraft={drawerDevice ? descJobs.getDraft(drawerDevice.id) : {}}
        saveJob={drawerDevice ? descJobs.getJob(drawerDevice.id) : null}
        learnJob={drawerDevice ? learnJobs.getJob(drawerDevice.id) : null}
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

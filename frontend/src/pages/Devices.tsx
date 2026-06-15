import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Divider,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Upload,
  App as AntApp,
  Popconfirm,
  Typography,
} from "antd";
import {
  PlusOutlined,
  DownloadOutlined,
  UploadOutlined,
  ApiOutlined,
  RocketOutlined,
  SettingOutlined,
  KeyOutlined,
  BookOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import type { Device, DeviceInterface, Paginated, Site, SnmpDefaults, SvidUsage } from "../api/types";
import { configPreviewModalProps, ConfigPreviewPre } from "../utils/configPreview";
import { formModalProps } from "../utils/formModal";
import {
  DEVICE_ROLE_OPTIONS,
  labelForOption,
  OVERLAY_OPTIONS,
  SNMP_VERSION_OPTIONS,
  VENDOR_OPTIONS,
} from "../constants/formOptions";
import { action, page as pageCopy, toast } from "../constants/uiCopy";
import { buildListQuery, dataTableProps, tablePagination } from "../utils/table";
import PageCard from "../components/PageCard";
import ListToolbar from "../components/ListToolbar";

const VENDOR_COLOR: Record<string, string> = {
  h3c: "blue",
  huawei: "red",
  juniper: "green",
  arista: "orange",
  cisco: "purple",
  frr: "cyan",
};
const STATUS_COLOR: Record<string, string> = {
  online: "green",
  offline: "red",
  maintenance: "orange",
  unknown: "default",
};
const VENDOR_AUTH_HINT: Record<string, string> = {
  h3c: "默认 NETCONF 830 / SSH 22；账号常为 admin 或 netconf",
  huawei: "默认 NETCONF 830；账号常为 netconf 或 huawei",
  juniper: "默认 NETCONF 830；账号常为 netconf",
  arista: "默认 SSH/eAPI；部分场景用 admin",
  cisco: "IOS-XR NETCONF 830；账号常为 admin / cisco",
  frr: "SSH 22，vtysh CLI；账号为 Linux 用户",
};

const FALLBACK_SNMP: SnmpDefaults = {
  enabled: true,
  port: 161,
  community: "bugis-ro",
  version: "2c",
};

export default function Devices() {
  const { message, modal } = AntApp.useApp();
  const [rows, setRows] = useState<Device[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [search, setSearch] = useState("");
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [credOpen, setCredOpen] = useState(false);
  const [credDevice, setCredDevice] = useState<Device | null>(null);
  const [snmpDefaults, setSnmpDefaults] = useState<SnmpDefaults>(FALLBACK_SNMP);
  const [form] = Form.useForm();
  const [credForm] = Form.useForm();
  const [learnOnImport, setLearnOnImport] = useState(true);
  const watchVendor = Form.useWatch("vendor", form);
  const watchSnmpEnabled = Form.useWatch("snmp_enabled", form);
  const [drawerDevice, setDrawerDevice] = useState<Device | null>(null);
  const [ifaces, setIfaces] = useState<DeviceInterface[]>([]);
  const [ifacesLoading, setIfacesLoading] = useState(false);

  async function loadIfaces(deviceId: number) {
    setIfacesLoading(true);
    try {
      const { data } = await api.get<DeviceInterface[]>(`/devices/${deviceId}/interfaces`);
      setIfaces(data);
    } finally {
      setIfacesLoading(false);
    }
  }

  async function openPorts(device: Device) {
    setDrawerDevice(device);
    setIfaces([]);
    await loadIfaces(device.id);
  }

  async function discover(deviceId: number) {
    const hide = message.loading("SNMP 接口扫描中…", 0);
    try {
      const { data } = await api.post<DeviceInterface[]>(
        `/devices/${deviceId}/discover-interfaces`,
      );
      hide();
      const simCount = data.filter((i) => i.discovered_via === "snmp-sim").length;
      if (simCount === data.length) {
        message.warning(
          "返回的是模拟数据（设备 SNMP 不可达或 Community 错误）。请检查管理 IP、UDP 161 与 Community 后重试",
        );
      } else if (simCount > 0) {
        message.warning(`部分接口为模拟数据（${simCount}/${data.length}），请检查 SNMP 配置`);
      } else {
        message.success(`SNMP 发现 ${data.length} 个接口`);
      }
      setIfaces(data);
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || toast.failed);
    }
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

  async function openCreateModal() {
    let defaults = FALLBACK_SNMP;
    try {
      const { data } = await api.get<SnmpDefaults>("/system/snmp-defaults");
      defaults = data;
      setSnmpDefaults(data);
    } catch {
      /* use fallback */
    }
    form.setFieldsValue({
      vendor: "h3c",
      role: "leaf",
      overlay_tech: "vxlan_evpn",
      status: "unknown",
      netconf_port: 830,
      ssh_port: 22,
      username: "admin",
      snmp_enabled: defaults.enabled,
      snmp_port: defaults.port,
      snmp_community: defaults.community,
      snmp_version: defaults.version,
    });
    setOpen(true);
  }

  async function onCreate() {
    const values = await form.validateFields();
    const payload = { ...values };
    if (!payload.password) delete payload.password;
    if (!payload.snmp_enabled) {
      payload.snmp_community = null;
    } else if (payload.snmp_community === snmpDefaults.community) {
      payload.snmp_community = null;
    }
    try {
      await api.post("/devices", payload);
      message.success("设备已纳管");
      setOpen(false);
      form.resetFields();
      load(1);
      setPage(1);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  function openCredEdit(d: Device) {
    setCredDevice(d);
    credForm.setFieldsValue({
      username: d.username || "",
      netconf_port: d.netconf_port ?? 830,
      ssh_port: d.ssh_port ?? 22,
      password: "",
    });
    setCredOpen(true);
  }

  async function saveCred() {
    if (!credDevice) return;
    const v = await credForm.validateFields();
    const payload: Record<string, unknown> = {
      username: v.username || null,
      netconf_port: v.netconf_port,
      ssh_port: v.ssh_port,
    };
    if (v.password) payload.password = v.password;
    try {
      await api.patch(`/devices/${credDevice.id}`, payload);
      message.success(toast.saved);
      setCredOpen(false);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  async function remove(id: number) {
    await api.delete(`/devices/${id}`);
    message.success(toast.deleted);
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
      load(1);
      setPage(1);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
    return false;
  }

  async function learnConfig(d: Device) {
    const hide = message.loading(`现网配置学习中 · ${d.name}...`, 0);
    try {
      const { data } = await api.post(`/devices/${d.id}/learn`);
      hide();
      if (data.success) {
        const inv = data.inventory;
        message.success(
          `${d.name} 学习完成 · ${inv?.service_count ?? 0} 个业务 · v${data.snapshot_version}`
        );
        if (data.svid_scan?.ports_scanned) {
          loadIfaces(d.id);
        }
      } else {
        message.error(data.error || toast.failed);
      }
      load();
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  async function initialize(d: Device) {
    const { data: bl } = await api.get(`/devices/${d.id}/baseline`);
    modal.confirm({
      title: `基线初始化 · ${d.name} (${d.vendor})`,
      ...configPreviewModalProps,
      icon: null,
      content: (
        <div>
          <div style={{ marginBottom: 8, color: "#888" }}>
            标准基线预览（管理 / Loopback / Underlay / EVPN Overlay）· 确认后 dry-run 下发并归档初始化快照
          </div>
          <ConfigPreviewPre>{bl.content}</ConfigPreviewPre>
        </div>
      ),
      okText: "下发基线配置",
      onOk: async () => {
        const { data } = await api.post(`/devices/${d.id}/initialize`);
        message.success(`${data.device} 初始化完成 · v${data.version} · ${data.transport}`);
        load();
      },
    });
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
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  function renderSvidUsage(list?: SvidUsage[] | null) {
    if (!list?.length) return "-";
    return (
      <Space size={[4, 4]} wrap>
        {list.map((u, idx) => {
          const label =
            u.access_mode === "access"
              ? "untagged"
              : u.c_vid
                ? `S:${u.s_vid}/C:${u.c_vid}`
                : `S:${u.s_vid}`;
          const color =
            u.source === "legacy" ? "red" : u.source === "device" ? "orange" : "blue";
          const tip = [
            u.circuit_code && `专线 ${u.circuit_code}`,
            u.source && `来源 ${u.source}`,
            u.note,
          ]
            .filter(Boolean)
            .join(" · ");
          return (
            <Tooltip key={idx} title={tip || label}>
              <Tag color={color}>{label}</Tag>
            </Tooltip>
          );
        })}
      </Space>
    );
  }

  const siteName = (id?: number) => sites.find((s) => s.id === id)?.code || "-";

  return (
    <PageCard
      title={pageCopy.devices}
      extra={
        <Space>
          <Link to="/settings/snmp">
            <Button icon={<SettingOutlined />}>SNMP 全局设置</Button>
          </Link>
          <Button icon={<DownloadOutlined />} onClick={exportCsv}>
            {action.export} CSV
          </Button>
          <Upload accept=".csv" showUploadList={false} beforeUpload={importCsv}>
            <Button icon={<UploadOutlined />}>{action.import} CSV</Button>
          </Upload>
          <Tooltip title="导入后自动拉取现网 running-config 并解析业务/VLAN 占用">
            <Switch
              checkedChildren="导入即学习"
              unCheckedChildren="仅导入"
              checked={learnOnImport}
              onChange={setLearnOnImport}
            />
          </Tooltip>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
            纳管设备
          </Button>
        </Space>
      }
    >
      <ListToolbar
        summary={`共 ${total.toLocaleString()} 台设备`}
        left={
          <Input.Search
            allowClear
            placeholder="搜索设备名称、主机名或管理 IP"
            style={{ width: 320 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onSearch={() => {
              setPage(1);
              load(1, pageSize, search);
            }}
            enterButton={<SearchOutlined />}
          />
        }
      />

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        {...dataTableProps(1500, rows.length > 0)}
        pagination={tablePagination(total, page, pageSize, (p, ps) => {
          setPage(p);
          setPageSize(ps);
        })}
        columns={[
          { title: "名称", dataIndex: "name", width: 140, ellipsis: true },
          {
            title: "厂商",
            dataIndex: "vendor",
            width: 120,
            ellipsis: true,
            render: (v) => (
              <Tooltip title={labelForOption(VENDOR_OPTIONS, v)}>
                <Tag color={VENDOR_COLOR[v]}>{labelForOption(VENDOR_OPTIONS, v)}</Tag>
              </Tooltip>
            ),
          },
          { title: "型号", dataIndex: "model", width: 120, ellipsis: true },
          {
            title: "角色",
            dataIndex: "role",
            width: 120,
            ellipsis: true,
            render: (r) => (
              <Tooltip title={labelForOption(DEVICE_ROLE_OPTIONS, r)}>
                <Tag>{labelForOption(DEVICE_ROLE_OPTIONS, r)}</Tag>
              </Tooltip>
            ),
          },
          {
            title: "Overlay",
            dataIndex: "overlay_tech",
            width: 130,
            render: (o) => (
              <Tag color={o === "vxlan_evpn" ? "blue" : "purple"}>
                {o === "vxlan_evpn" ? "VXLAN-EVPN" : "SR-MPLS-EVPN"}
              </Tag>
            ),
          },
          { title: "管理IP", dataIndex: "mgmt_ip", width: 120 },
          {
            title: "凭证",
            width: 88,
            render: (_, r) =>
              r.password_set || r.username ? (
                <Tag color="green">已配置</Tag>
              ) : (
                <Tag>未配置</Tag>
              ),
          },
          {
            title: "SNMP",
            width: 88,
            render: (_, r) =>
              r.snmp_enabled === false ? (
                <Tag>关闭</Tag>
              ) : (
                <Tag color="blue">{r.snmp_version || "2c"}</Tag>
              ),
          },
          { title: "Loopback", dataIndex: "loopback_ip", width: 120 },
          { title: "ASN", dataIndex: "bgp_asn", width: 80 },
          { title: "站点", width: 80, render: (_, r) => siteName(r.site_id) },
          {
            title: "状态",
            dataIndex: "status",
            width: 90,
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "操作",
            width: 300,
            className: "table-actions",
            render: (_, r) => (
              <Space wrap size={4}>
                <a onClick={() => openPorts(r)}>端口</a>
                <a onClick={() => openCredEdit(r)}>
                  <KeyOutlined /> 凭证
                </a>
                <a onClick={() => learnConfig(r)}>
                  <BookOutlined /> 现网学习
                </a>
                <a onClick={() => initialize(r)}>
                  <RocketOutlined /> 初始化
                </a>
                <a onClick={() => check(r.id)}>检测</a>
                <a onClick={() => discover(r.id)}>
                  <ApiOutlined /> SNMP 发现
                </a>
                <Popconfirm title={`${action.confirm}${action.delete}？`} onConfirm={() => remove(r.id)}>
                  <a style={{ color: "#cf1322" }}>{action.delete}</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={drawerDevice ? `端口清单 · ${drawerDevice.name}` : "端口清单"}
        width={880}
        open={!!drawerDevice}
        onClose={() => setDrawerDevice(null)}
        extra={
          drawerDevice && (
            <Space>
              <Button onClick={() => check(drawerDevice.id)}>检测 S-VID</Button>
              <Button type="primary" onClick={() => discover(drawerDevice.id)}>
                SNMP 发现
              </Button>
            </Space>
          )
        }
      >
        {ifaces.some((i) => i.discovered_via === "snmp-sim") && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="部分端口为模拟数据"
            description="发现方式显示 snmp-sim 表示未从设备读到真实 IF-MIB（常见于 Community 错误或 UDP 161 不可达）。Dry-run 仅影响配置下发，不影响 SNMP 采集。请确认设备 SNMP Community 与平台「SNMP 采集」设置一致后重新发现。"
          />
        )}
        <Table
          size="small"
          rowKey={(r) => `${r.device_id}-${r.name}`}
          loading={ifacesLoading}
          dataSource={ifaces}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 个端口` }}
          columns={[
            { title: "接口", dataIndex: "name", width: 120 },
            {
              title: "描述",
              dataIndex: "description",
              ellipsis: true,
              render: (d: string) =>
                d ? (
                  <Tooltip title={d}>
                    {d.includes("bw(") ? <Tag color="purple">{d}</Tag> : d}
                  </Tooltip>
                ) : (
                  "-"
                ),
            },
            {
              title: "速率",
              dataIndex: "speed_mbps",
              width: 80,
              render: (s) => (s ? `${s >= 1000 ? s / 1000 + "G" : s + "M"}` : "-"),
            },
            {
              title: "Oper",
              dataIndex: "oper_status",
              width: 70,
              render: (s) => <Tag color={s === "up" ? "green" : "default"}>{s || "-"}</Tag>,
            },
            { title: "ifIndex", dataIndex: "ifindex", width: 70 },
            {
              title: "发现方式",
              dataIndex: "discovered_via",
              width: 90,
              render: (d) => d && <Tag>{d}</Tag>,
            },
            {
              title: "S-VID 占用",
              dataIndex: "used_s_vids",
              render: (v: SvidUsage[] | null) => renderSvidUsage(v),
            },
            {
              title: "占用",
              dataIndex: "allocated",
              width: 70,
              render: (a, row) =>
                a || row.used_s_vids?.length ? <Tag color="orange">已占用</Tag> : "-",
            },
          ]}
        />
      </Drawer>

      <Modal
        title="纳管设备"
        open={open}
        onOk={onCreate}
        onCancel={() => setOpen(false)}
        okText={action.create}
        {...formModalProps}
        width={840}
      >
        <Form form={form} layout="vertical" className="app-form">
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="远程登录凭证说明"
            description={
              <Typography.Paragraph style={{ marginBottom: 0 }}>
                <strong>配置下发 / 初始化</strong> 使用 NETCONF（或 SSH CLI）的 <strong>用户名 + 密码</strong>。
                <strong> SNMP 发现</strong> 走真实 IF-MIB 采集（与 Dry-run 无关）；请填写正确的只读 Community。
                Demo 环境 <strong>Dry-run</strong> 仅模拟配置下发，不会阻止 SNMP 端口发现。
              </Typography.Paragraph>
            }
          />
          <Row gutter={16}>
            <Col xs={24} sm={14}>
              <Form.Item name="name" label="名称" rules={[{ required: true }]}>
                <Input placeholder="BJ-LEAF-01" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={10}>
              <Form.Item name="vendor" label="厂商">
                <Select options={VENDOR_OPTIONS} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={10}>
              <Form.Item name="model" label="型号">
                <Input placeholder="S6850 / CE12800 / MX204 ..." />
              </Form.Item>
            </Col>
            <Col xs={24} sm={7}>
              <Form.Item name="role" label="角色">
                <Select options={DEVICE_ROLE_OPTIONS} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={7}>
              <Form.Item name="overlay_tech" label="Overlay">
                <Select options={OVERLAY_OPTIONS} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={8}>
              <Form.Item name="mgmt_ip" label="管理 IP" rules={[{ required: true }]}>
                <Input placeholder="10.1.0.11" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="loopback_ip" label="Loopback">
                <Input placeholder="10.1.255.11" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="bgp_asn" label="BGP ASN">
                <InputNumber style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16} align="bottom">
            <Col xs={24} sm={10}>
              <Form.Item name="site_id" label="数据中心">
                <Select
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  options={sites.map((s) => ({ value: s.id, label: `${s.code} · ${s.name}` }))}
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item name="sr_node_sid" label="SR Node-SID">
                <InputNumber style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={6}>
              <Form.Item name="is_route_reflector" label="路由反射器" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" style={{ margin: "8px 0 16px" }}>
            南向登录凭证
          </Divider>
          {watchVendor && VENDOR_AUTH_HINT[watchVendor] && (
            <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
              {VENDOR_AUTH_HINT[watchVendor]}
            </Typography.Text>
          )}
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item name="username" label="用户名 (NETCONF / SSH)">
                <Input placeholder="admin / netconf" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item
                name="password"
                label="密码 / SNMP Community"
                extra="SNMP 可在「系统设置 → SNMP 采集」配置全局 Community；此处可覆盖单台设备"
              >
                <Input.Password placeholder="登录密码或只读 community" autoComplete="new-password" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item name="netconf_port" label="NETCONF 端口">
                <InputNumber min={1} max={65535} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item name="ssh_port" label="SSH 端口">
                <InputNumber min={1} max={65535} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" style={{ margin: "8px 0 12px" }}>
            SNMP 采集（可选）
          </Divider>
          <Typography.Paragraph type="secondary" style={{ marginTop: 0, marginBottom: 12 }}>
            默认继承平台配置（Community <Typography.Text code>{snmpDefaults.community}</Typography.Text> · UDP {snmpDefaults.port}）。
            关闭后跳过 SNMP 接口发现（Dry-run 下仍可模拟）。
          </Typography.Paragraph>
          <Form.Item name="snmp_enabled" label="启用 SNMP" valuePropName="checked">
            <Switch checkedChildren="开" unCheckedChildren="关" />
          </Form.Item>
          <Collapse
            ghost
            activeKey={watchSnmpEnabled ? ["snmp"] : []}
            items={[
              {
                key: "snmp",
                label: "高级参数（留空则使用平台默认）",
                children: (
                  <Row gutter={16}>
                    <Col xs={24} sm={12}>
                      <Form.Item name="snmp_community" label="Community">
                        <Input placeholder={snmpDefaults.community} disabled={!watchSnmpEnabled} allowClear />
                      </Form.Item>
                    </Col>
                    <Col xs={24} sm={6}>
                      <Form.Item name="snmp_port" label="UDP 端口">
                        <InputNumber min={1} max={65535} style={{ width: "100%" }} disabled={!watchSnmpEnabled} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} sm={6}>
                      <Form.Item name="snmp_version" label="版本">
                        <Select disabled={!watchSnmpEnabled} options={SNMP_VERSION_OPTIONS} />
                      </Form.Item>
                    </Col>
                  </Row>
                ),
              },
            ]}
          />
        </Form>
      </Modal>

      <Modal
        title={credDevice ? `设备凭证 · ${credDevice.name}` : "设备凭证"}
        open={credOpen}
        onOk={saveCred}
        onCancel={() => setCredOpen(false)}
        okText={action.save}
        {...formModalProps}
        width={520}
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="密码不会回显"
          description="留空密码则保持原值不变。修改后可用于 NETCONF/SSH 下发与 SNMP（若启用设备凭证优先）。"
        />
        <Form form={credForm} layout="vertical" className="app-form">
          <Form.Item name="username" label="用户名">
            <Input placeholder="admin / netconf" />
          </Form.Item>
          <Form.Item name="password" label="密码 / SNMP Community">
            <Input.Password placeholder="留空不修改" autoComplete="new-password" />
          </Form.Item>
          <Row gutter={16}>
            <Col xs={24} sm={12}>
              <Form.Item name="netconf_port" label="NETCONF 端口">
                <InputNumber min={1} max={65535} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item name="ssh_port" label="SSH 端口">
                <InputNumber min={1} max={65535} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </PageCard>
  );
}

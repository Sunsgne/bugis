import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
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
import { PlusOutlined, DownloadOutlined, UploadOutlined, ApiOutlined, RocketOutlined, SettingOutlined, KeyOutlined, BookOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Device, DeviceInterface, Site, SvidUsage } from "../api/types";
import { configPreviewModalProps, ConfigPreviewPre } from "../utils/configPreview";

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
const ROLES = ["spine", "leaf", "border_leaf", "vtep", "pe", "p", "rr", "dci_gw", "cpe"];
const OVERLAYS = ["vxlan_evpn", "srmpls_evpn"];
const VENDORS = ["h3c", "huawei", "juniper", "arista", "cisco", "frr"];

const VENDOR_AUTH_HINT: Record<string, string> = {
  h3c: "默认 NETCONF 830 / SSH 22；账号常为 admin 或 netconf",
  huawei: "默认 NETCONF 830；账号常为 netconf 或 huawei",
  juniper: "默认 NETCONF 830；账号常为 netconf",
  arista: "默认 SSH/eAPI；部分场景用 admin",
  cisco: "IOS-XR NETCONF 830；账号常为 admin / cisco",
  frr: "SSH 22，vtysh CLI；账号为 Linux 用户",
};

export default function Devices() {
  const { message, modal } = AntApp.useApp();
  const [rows, setRows] = useState<Device[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [credOpen, setCredOpen] = useState(false);
  const [credDevice, setCredDevice] = useState<Device | null>(null);
  const [form] = Form.useForm();
  const [credForm] = Form.useForm();
  const [ifaces, setIfaces] = useState<Record<number, DeviceInterface[]>>({});
  const [learnOnImport, setLearnOnImport] = useState(true);
  const watchVendor = Form.useWatch("vendor", form);

  async function loadIfaces(deviceId: number) {
    const { data } = await api.get<DeviceInterface[]>(`/devices/${deviceId}/interfaces`);
    setIfaces((p) => ({ ...p, [deviceId]: data }));
  }

  async function discover(deviceId: number) {
    const hide = message.loading("SNMP 接口发现中...", 0);
    try {
      const { data } = await api.post<DeviceInterface[]>(
        `/devices/${deviceId}/discover-interfaces`
      );
      hide();
      message.success(`已发现 ${data.length} 个接口`);
      setIfaces((p) => ({ ...p, [deviceId]: data }));
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || "发现失败");
    }
  }

  async function load() {
    setLoading(true);
    try {
      const [d, s] = await Promise.all([
        api.get<Device[]>("/devices"),
        api.get<Site[]>("/sites"),
      ]);
      setRows(d.data);
      setSites(s.data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function onCreate() {
    const values = await form.validateFields();
    const payload = { ...values };
    if (!payload.password) delete payload.password;
    try {
      await api.post("/devices", payload);
      message.success("设备已添加");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
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
      message.success("设备凭证已保存");
      setCredOpen(false);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  async function remove(id: number) {
    await api.delete(`/devices/${id}`);
    message.success("已删除");
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
      message.success(`导入完成: 新增 ${data.created}, 跳过 ${data.skipped}${learnMsg}`);
      if (data.errors?.length) message.warning(`${data.errors.length} 行有误`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "导入失败");
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
        message.error(data.error || "学习失败");
      }
      load();
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || "学习失败");
    }
  }

  async function initialize(d: Device) {
    const { data: bl } = await api.get(`/devices/${d.id}/baseline`);
    modal.confirm({
      title: `设备初始化 · ${d.name} (${d.vendor})`,
      ...configPreviewModalProps,
      icon: null,
      content: (
        <div>
          <div style={{ marginBottom: 8, color: "#888" }}>
            标准基线配置(管理/Loopback/Underlay/EVPN Overlay)预览,确认后下发(dry-run)并保存为初始化快照:
          </div>
          <ConfigPreviewPre>{bl.content}</ConfigPreviewPre>
        </div>
      ),
      okText: "下发初始化配置",
      onOk: async () => {
        const { data } = await api.post(`/devices/${d.id}/initialize`);
        message.success(`${data.device} 初始化完成 (v${data.version}, ${data.transport})`);
        load();
      },
    });
  }

  async function check(id: number) {
    const hide = message.loading("设备检测中 (可达性 + S-VID 占用)...", 0);
    try {
      const { data } = await api.post(`/devices/${id}/check`);
      hide();
      if (data.reachable) {
        const scan = data.svid_scan;
        const svidCount = scan?.total_s_vids ?? 0;
        const conflictCount = scan?.conflicts?.length ?? 0;
        if (conflictCount > 0) {
          message.warning(
            `${data.device} 可达 · 发现 ${svidCount} 个 S-VID · ${conflictCount} 处冲突`
          );
        } else {
          message.success(
            `${data.device} 可达 (${data.latency_ms}ms) · 已扫描 ${svidCount} 个 S-VID 占用`
          );
        }
        setIfaces((p) => {
          const ports = scan?.ports as Array<{ interface: string; s_vids: SvidUsage[]; allocated: boolean }> | undefined;
          if (!ports?.length) return p;
          const byName = Object.fromEntries(ports.map((row) => [row.interface, row]));
          const existing = p[id] || [];
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
          return { ...p, [id]: merged };
        });
      } else {
        message.error(`${data.device} 不可达 (${data.mgmt_ip})`);
      }
      load();
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || "检测失败");
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
    <Card
      title="设备管理"
      extra={
        <Space>
          <Link to="/settings/snmp">
            <Button icon={<SettingOutlined />}>SNMP 全局设置</Button>
          </Link>
          <Button icon={<DownloadOutlined />} onClick={exportCsv}>
            导出 CSV
          </Button>
          <Upload accept=".csv" showUploadList={false} beforeUpload={importCsv}>
            <Button icon={<UploadOutlined />}>导入 CSV</Button>
          </Upload>
          <Tooltip title="导入后自动拉取现网 running-config 并解析业务/VLAN 占用">
            <Switch
              checkedChildren="导入即学习"
              unCheckedChildren="仅导入"
              checked={learnOnImport}
              onChange={setLearnOnImport}
            />
          </Tooltip>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            添加设备
          </Button>
        </Space>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        expandable={{
          onExpand: (expanded, r) => {
            if (expanded && !ifaces[r.id]) loadIfaces(r.id);
          },
          expandedRowRender: (r) => {
            const list = ifaces[r.id] || [];
            return list.length ? (
              <Table
                size="small"
                rowKey="id"
                pagination={false}
                dataSource={list}
                columns={[
                  { title: "接口", dataIndex: "name" },
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
                    render: (s) => (s ? `${s >= 1000 ? s / 1000 + "G" : s + "M"}` : "-"),
                  },
                  {
                    title: "Oper",
                    dataIndex: "oper_status",
                    render: (s) => <Tag color={s === "up" ? "green" : "default"}>{s || "-"}</Tag>,
                  },
                  { title: "ifIndex", dataIndex: "ifindex" },
                  {
                    title: "发现方式",
                    dataIndex: "discovered_via",
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
                    render: (a, row) =>
                      a || row.used_s_vids?.length ? (
                        <Tag color="orange">已占用</Tag>
                      ) : (
                        "-"
                      ),
                  },
                ]}
              />
            ) : (
              <span style={{ color: "#888" }}>暂无接口，点击「SNMP 发现」</span>
            );
          },
        }}
        columns={[
          { title: "名称", dataIndex: "name" },
          {
            title: "厂商",
            dataIndex: "vendor",
            render: (v) => <Tag color={VENDOR_COLOR[v]}>{v.toUpperCase()}</Tag>,
          },
          { title: "型号", dataIndex: "model" },
          { title: "角色", dataIndex: "role", render: (r) => <Tag>{r}</Tag> },
          {
            title: "Overlay",
            dataIndex: "overlay_tech",
            render: (o) => (
              <Tag color={o === "vxlan_evpn" ? "blue" : "purple"}>
                {o === "vxlan_evpn" ? "VXLAN-EVPN" : "SR-MPLS-EVPN"}
              </Tag>
            ),
          },
          { title: "管理IP", dataIndex: "mgmt_ip" },
          {
            title: "凭证",
            width: 100,
            render: (_, r) =>
              r.password_set || r.username ? (
                <Tag color="green">已配置</Tag>
              ) : (
                <Tag>未配置</Tag>
              ),
          },
          { title: "Loopback", dataIndex: "loopback_ip" },
          { title: "ASN", dataIndex: "bgp_asn" },
          { title: "站点", render: (_, r) => siteName(r.site_id) },
          {
            title: "状态",
            dataIndex: "status",
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "操作",
            render: (_, r) => (
              <Space wrap>
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
                  <ApiOutlined /> SNMP发现
                </a>
                <Popconfirm title="确认删除?" onConfirm={() => remove(r.id)}>
                  <a style={{ color: "#cf1322" }}>删除</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal
        title="添加设备"
        open={open}
        onOk={onCreate}
        onCancel={() => setOpen(false)}
        width={720}
        okText="添加"
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            vendor: "h3c",
            role: "leaf",
            overlay_tech: "vxlan_evpn",
            status: "unknown",
            netconf_port: 830,
            ssh_port: 22,
            username: "admin",
          }}
        >
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="远程登录凭证说明"
            description={
              <Typography.Paragraph style={{ marginBottom: 0 }}>
                <strong>配置下发 / 初始化</strong> 使用 NETCONF（或 SSH CLI）的 <strong>用户名 + 密码</strong>。
                <strong> SNMP 发现</strong> 默认读全局 SNMP 设置；若开启「优先设备凭证」，本页密码字段同时作为该设备的只读 Community。
                Demo 环境默认 <strong>Dry-run</strong>，检测仅模拟可达；关闭 Dry-run 后才会真实登录设备。
              </Typography.Paragraph>
            }
          />
          <Space size="middle" style={{ display: "flex", flexWrap: "wrap" }}>
            <Form.Item name="name" label="名称" rules={[{ required: true }]} style={{ flex: "1 1 200px" }}>
              <Input placeholder="BJ-LEAF-01" />
            </Form.Item>
            <Form.Item name="vendor" label="厂商" style={{ flex: "0 1 140px" }}>
              <Select options={VENDORS.map((v) => ({ value: v, label: v.toUpperCase() }))} />
            </Form.Item>
          </Space>
          <Space size="middle" style={{ display: "flex", flexWrap: "wrap" }}>
            <Form.Item name="model" label="型号" style={{ flex: "1 1 200px" }}>
              <Input placeholder="S6850 / CE12800 / MX204 ..." />
            </Form.Item>
            <Form.Item name="role" label="角色" style={{ flex: "0 1 140px" }}>
              <Select options={ROLES.map((v) => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="overlay_tech" label="Overlay" style={{ flex: "0 1 160px" }}>
              <Select options={OVERLAYS.map((v) => ({ value: v, label: v }))} />
            </Form.Item>
          </Space>
          <Space size="middle" style={{ display: "flex", flexWrap: "wrap" }}>
            <Form.Item name="mgmt_ip" label="管理 IP" rules={[{ required: true }]} style={{ flex: "1 1 180px" }}>
              <Input placeholder="10.1.0.11" />
            </Form.Item>
            <Form.Item name="loopback_ip" label="Loopback" style={{ flex: "1 1 180px" }}>
              <Input placeholder="10.1.255.11" />
            </Form.Item>
            <Form.Item name="bgp_asn" label="BGP ASN" style={{ flex: "0 1 120px" }}>
              <InputNumber style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Space size="middle" style={{ display: "flex", flexWrap: "wrap" }}>
            <Form.Item name="site_id" label="数据中心" style={{ flex: "1 1 200px" }}>
              <Select
                allowClear
                options={sites.map((s) => ({ value: s.id, label: `${s.code} ${s.name}` }))}
              />
            </Form.Item>
            <Form.Item name="sr_node_sid" label="SR Node-SID" style={{ flex: "0 1 140px" }}>
              <InputNumber style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="is_route_reflector" label="路由反射器" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>

          <Divider orientation="left" style={{ margin: "8px 0 16px" }}>
            南向登录凭证
          </Divider>
          {watchVendor && VENDOR_AUTH_HINT[watchVendor] && (
            <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
              {VENDOR_AUTH_HINT[watchVendor]}
            </Typography.Text>
          )}
          <Space size="middle" style={{ display: "flex", flexWrap: "wrap" }}>
            <Form.Item name="username" label="用户名 (NETCONF / SSH)" style={{ flex: "1 1 200px" }}>
              <Input placeholder="admin / netconf" />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码 / SNMP Community"
              extra="SNMP 可在「系统设置 → SNMP 采集」配置全局 Community；此处可覆盖单台设备"
              style={{ flex: "1 1 200px" }}
            >
              <Input.Password placeholder="登录密码或只读 community" autoComplete="new-password" />
            </Form.Item>
          </Space>
          <Space size="middle" style={{ display: "flex", flexWrap: "wrap" }}>
            <Form.Item name="netconf_port" label="NETCONF 端口" style={{ flex: "0 1 120px" }}>
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="ssh_port" label="SSH 端口" style={{ flex: "0 1 120px" }}>
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      <Modal
        title={credDevice ? `设备凭证 · ${credDevice.name}` : "设备凭证"}
        open={credOpen}
        onOk={saveCred}
        onCancel={() => setCredOpen(false)}
        width={520}
        okText="保存"
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="密码不会回显"
          description="留空密码则保持原值不变。修改后可用于 NETCONF/SSH 下发与 SNMP（若启用设备凭证优先）。"
        />
        <Form form={credForm} layout="vertical">
          <Form.Item name="username" label="用户名">
            <Input placeholder="admin / netconf" />
          </Form.Item>
          <Form.Item name="password" label="密码 / SNMP Community">
            <Input.Password placeholder="留空不修改" autoComplete="new-password" />
          </Form.Item>
          <Space size="middle" style={{ display: "flex" }}>
            <Form.Item name="netconf_port" label="NETCONF 端口" style={{ flex: 1 }}>
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="ssh_port" label="SSH 端口" style={{ flex: 1 }}>
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Card>
  );
}

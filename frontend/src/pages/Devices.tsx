import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Upload,
  App as AntApp,
  Popconfirm,
} from "antd";
import { PlusOutlined, DownloadOutlined, UploadOutlined, ApiOutlined, RocketOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Device, DeviceInterface, Site } from "../api/types";

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

export default function Devices() {
  const { message, modal } = AntApp.useApp();
  const [rows, setRows] = useState<Device[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const [ifaces, setIfaces] = useState<Record<number, DeviceInterface[]>>({});

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
    try {
      await api.post("/devices", values);
      message.success("设备已添加");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
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
      const { data } = await api.post("/bulk/devices/import", fd);
      message.success(`导入完成: 新增 ${data.created}, 跳过 ${data.skipped}`);
      if (data.errors?.length) message.warning(`${data.errors.length} 行有误`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "导入失败");
    }
    return false;
  }

  async function initialize(d: Device) {
    const { data: bl } = await api.get(`/devices/${d.id}/baseline`);
    modal.confirm({
      title: `设备初始化 · ${d.name} (${d.vendor})`,
      width: 760,
      icon: null,
      content: (
        <div>
          <div style={{ marginBottom: 8, color: "#888" }}>
            标准基线配置(管理/Loopback/Underlay/EVPN Overlay)预览,确认后下发(dry-run)并保存为初始化快照:
          </div>
          <pre className="config-pre">{bl.content}</pre>
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
    const { data } = await api.post(`/devices/${id}/check`);
    if (data.reachable) {
      message.success(`${data.device} 可达, 时延 ${data.latency_ms}ms`);
    } else {
      message.error(`${data.device} 不可达 (${data.mgmt_ip})`);
    }
    load();
  }

  const siteName = (id?: number) => sites.find((s) => s.id === id)?.code || "-";

  return (
    <Card
      title="设备管理"
      extra={
        <Space>
          <Button icon={<DownloadOutlined />} onClick={exportCsv}>
            导出 CSV
          </Button>
          <Upload accept=".csv" showUploadList={false} beforeUpload={importCsv}>
            <Button icon={<UploadOutlined />}>导入 CSV</Button>
          </Upload>
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
                    title: "占用",
                    dataIndex: "allocated",
                    render: (a) => (a ? <Tag color="orange">已占用</Tag> : "-"),
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
              <Space>
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
        width={620}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            vendor: "h3c",
            role: "leaf",
            overlay_tech: "vxlan_evpn",
            status: "online",
            netconf_port: 830,
            ssh_port: 22,
          }}
        >
          <Space size="middle" style={{ display: "flex" }}>
            <Form.Item name="name" label="名称" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Input placeholder="BJ-LEAF-01" />
            </Form.Item>
            <Form.Item name="vendor" label="厂商" style={{ width: 140 }}>
              <Select options={VENDORS.map((v) => ({ value: v, label: v.toUpperCase() }))} />
            </Form.Item>
          </Space>
          <Space size="middle" style={{ display: "flex" }}>
            <Form.Item name="model" label="型号" style={{ flex: 1 }}>
              <Input placeholder="S6850 / CE12800 / MX204 ..." />
            </Form.Item>
            <Form.Item name="role" label="角色" style={{ width: 140 }}>
              <Select options={ROLES.map((v) => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="overlay_tech" label="Overlay" style={{ width: 160 }}>
              <Select options={OVERLAYS.map((v) => ({ value: v, label: v }))} />
            </Form.Item>
          </Space>
          <Space size="middle" style={{ display: "flex" }}>
            <Form.Item name="mgmt_ip" label="管理 IP" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Input placeholder="10.1.0.11" />
            </Form.Item>
            <Form.Item name="loopback_ip" label="Loopback" style={{ flex: 1 }}>
              <Input placeholder="10.1.255.11" />
            </Form.Item>
            <Form.Item name="bgp_asn" label="BGP ASN" style={{ width: 120 }}>
              <InputNumber style={{ width: "100%" }} />
            </Form.Item>
          </Space>
          <Space size="middle" style={{ display: "flex" }}>
            <Form.Item name="site_id" label="数据中心" style={{ flex: 1 }}>
              <Select
                allowClear
                options={sites.map((s) => ({ value: s.id, label: `${s.code} ${s.name}` }))}
              />
            </Form.Item>
            <Form.Item name="sr_node_sid" label="SR Node-SID" style={{ width: 140 }}>
              <InputNumber style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="is_route_reflector" label="路由反射器" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </Card>
  );
}

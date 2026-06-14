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
  App as AntApp,
  Popconfirm,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Device, Site } from "../api/types";

const VENDOR_COLOR: Record<string, string> = {
  h3c: "blue",
  huawei: "red",
  juniper: "green",
  arista: "orange",
  cisco: "purple",
};
const STATUS_COLOR: Record<string, string> = {
  online: "green",
  offline: "red",
  maintenance: "orange",
  unknown: "default",
};
const ROLES = ["spine", "leaf", "border_leaf", "vtep", "pe", "p", "rr", "dci_gw", "cpe"];
const OVERLAYS = ["vxlan_evpn", "srmpls_evpn"];
const VENDORS = ["h3c", "huawei", "juniper", "arista", "cisco"];

export default function Devices() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Device[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

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

  const siteName = (id?: number) => sites.find((s) => s.id === id)?.code || "-";

  return (
    <Card
      title="设备管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          添加设备
        </Button>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
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
              <Popconfirm title="确认删除?" onConfirm={() => remove(r.id)}>
                <a style={{ color: "#cf1322" }}>删除</a>
              </Popconfirm>
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

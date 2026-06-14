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
  Table,
  Tag,
  Tooltip,
  App as AntApp,
  Popconfirm,
  Descriptions,
} from "antd";
import { PlusOutlined, ThunderboltOutlined, EyeOutlined, MinusCircleOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Circuit, Device, Tenant } from "../api/types";

const SERVICE_LABEL: Record<string, string> = {
  l2vpn_evpn: "EVPN L2VPN",
  l3vpn_evpn: "EVPN L3VPN",
  evpn_vpws: "EVPN-VPWS",
  dci: "DCI 互联",
};
const STATUS_COLOR: Record<string, string> = {
  draft: "default",
  pending: "gold",
  provisioning: "processing",
  active: "green",
  degraded: "orange",
  suspended: "volcano",
  decommissioned: "default",
  failed: "red",
};

export default function Circuits() {
  const { message, modal } = AntApp.useApp();
  const [rows, setRows] = useState<Circuit[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    setLoading(true);
    try {
      const [c, t, d] = await Promise.all([
        api.get<Circuit[]>("/circuits"),
        api.get<Tenant[]>("/tenants"),
        api.get<Device[]>("/devices"),
      ]);
      setRows(c.data);
      setTenants(t.data);
      setDevices(d.data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  const tenantName = (id: number) => tenants.find((t) => t.id === id)?.name || id;
  const deviceName = (id: number) => devices.find((d) => d.id === id)?.name || id;

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post("/circuits", values);
      message.success("专线已创建（草稿），可点击开通下发配置");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function provision(c: Circuit) {
    try {
      const { data } = await api.post(`/work-orders/provision/${c.id}`);
      message.success(`开通工单 ${data.code}: ${data.status}`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "开通失败");
    }
  }

  async function decommission(c: Circuit) {
    try {
      const { data } = await api.post(
        `/work-orders/provision/${c.id}?wo_type=decommission`
      );
      message.success(`拆除工单 ${data.code}: ${data.status}`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "拆除失败");
    }
  }

  async function preview(c: Circuit) {
    const wo = await api.post(`/work-orders`, { circuit_id: c.id, type: "provision" });
    const { data } = await api.get(`/work-orders/${wo.data.id}/preview`);
    modal.info({
      title: `配置预览 · ${c.code} (${c.name})`,
      width: 760,
      content: (
        <div style={{ maxHeight: 480, overflow: "auto" }}>
          {data.previews.map((p: any, i: number) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <Tag color="blue">{p.vendor.toUpperCase()}</Tag>
              <b>{p.device}</b> <Tag>{p.transport}</Tag>
              <pre className="config-pre">{p.config}</pre>
            </div>
          ))}
        </div>
      ),
    });
  }

  return (
    <Card
      title="专线管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新建专线
        </Button>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        expandable={{
          expandedRowRender: (r) => (
            <Descriptions size="small" column={3} bordered>
              <Descriptions.Item label="VNI">{r.vni}</Descriptions.Item>
              <Descriptions.Item label="VLAN">{r.vlan_id}</Descriptions.Item>
              <Descriptions.Item label="VRF">{r.vrf_name}</Descriptions.Item>
              <Descriptions.Item label="RD">{r.route_distinguisher}</Descriptions.Item>
              <Descriptions.Item label="RT">{r.route_target}</Descriptions.Item>
              <Descriptions.Item label="MTU">{r.mtu}</Descriptions.Item>
              <Descriptions.Item label="端点" span={3}>
                {r.endpoints.map((e) => (
                  <Tag key={e.id}>
                    {e.label}: {deviceName(e.device_id)} / {e.interface_name}
                  </Tag>
                ))}
              </Descriptions.Item>
            </Descriptions>
          ),
        }}
        columns={[
          { title: "编码", dataIndex: "code" },
          { title: "名称", dataIndex: "name" },
          { title: "租户", render: (_, r) => tenantName(r.tenant_id) },
          {
            title: "业务类型",
            dataIndex: "service_type",
            render: (s) => <Tag color="geekblue">{SERVICE_LABEL[s] || s}</Tag>,
          },
          { title: "VNI", dataIndex: "vni" },
          {
            title: "带宽",
            dataIndex: "bandwidth_mbps",
            render: (b) => `${b} Mbps`,
          },
          { title: "SLA", dataIndex: "sla_target", render: (s) => s && <Tag>{s}%</Tag> },
          {
            title: "状态",
            dataIndex: "status",
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "操作",
            width: 240,
            render: (_, r) => (
              <Space>
                <Tooltip title="一键开通（下发配置, dry-run）">
                  <Button
                    size="small"
                    type="primary"
                    icon={<ThunderboltOutlined />}
                    onClick={() => provision(r)}
                    disabled={r.status === "active"}
                  >
                    开通
                  </Button>
                </Tooltip>
                <Tooltip title="预览各厂商配置">
                  <Button size="small" icon={<EyeOutlined />} onClick={() => preview(r)} />
                </Tooltip>
                <Popconfirm title="确认拆除该专线?" onConfirm={() => decommission(r)}>
                  <Button size="small" danger icon={<MinusCircleOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <CreateModal
        open={open}
        form={form}
        tenants={tenants}
        devices={devices}
        onOk={onCreate}
        onCancel={() => setOpen(false)}
      />
    </Card>
  );
}

function CreateModal({ open, form, tenants, devices, onOk, onCancel }: any) {
  return (
    <Modal title="新建专线" open={open} onOk={onOk} onCancel={onCancel} width={680}>
      <Form
        form={form}
        layout="vertical"
        initialValues={{ service_type: "l2vpn_evpn", bandwidth_mbps: 100, mtu: 9000, endpoints: [{ label: "A" }, { label: "Z" }] }}
      >
        <Space size="middle" style={{ display: "flex" }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]} style={{ flex: 1 }}>
            <Input placeholder="例如 银行北京-上海二层专线" />
          </Form.Item>
          <Form.Item name="tenant_id" label="租户" rules={[{ required: true }]} style={{ width: 200 }}>
            <Select
              options={tenants.map((t: Tenant) => ({ value: t.id, label: `${t.code} ${t.name}` }))}
            />
          </Form.Item>
        </Space>
        <Space size="middle" style={{ display: "flex" }}>
          <Form.Item name="service_type" label="业务类型" style={{ flex: 1 }}>
            <Select
              options={Object.entries(SERVICE_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="bandwidth_mbps" label="带宽(Mbps)" style={{ width: 140 }}>
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="sla_target" label="SLA(%)" style={{ width: 120 }}>
            <Input placeholder="99.95" />
          </Form.Item>
        </Space>

        <div style={{ fontWeight: 600, marginBottom: 8 }}>接入端点</div>
        <Form.List name="endpoints">
          {(fields, { add, remove }) => (
            <>
              {fields.map((field) => (
                <Space key={field.key} align="baseline" style={{ display: "flex" }}>
                  <Form.Item name={[field.name, "label"]} rules={[{ required: true }]}>
                    <Input placeholder="标签 A/Z" style={{ width: 80 }} />
                  </Form.Item>
                  <Form.Item name={[field.name, "device_id"]} rules={[{ required: true }]}>
                    <Select
                      style={{ width: 240 }}
                      placeholder="选择设备"
                      options={devices.map((d: Device) => ({
                        value: d.id,
                        label: `${d.name} (${d.vendor})`,
                      }))}
                    />
                  </Form.Item>
                  <Form.Item name={[field.name, "interface_name"]} rules={[{ required: true }]}>
                    <Input placeholder="接口 GE1/0/1" style={{ width: 140 }} />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(field.name)} />
                </Space>
              ))}
              <Button type="dashed" block icon={<PlusOutlined />} onClick={() => add({ label: "" })}>
                添加端点
              </Button>
            </>
          )}
        </Form.List>
      </Form>
    </Modal>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  App as AntApp,
  Popconfirm,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Tenant } from "../api/types";
import { action, page, toast } from "../constants/uiCopy";

const TYPE_LABEL: Record<string, string> = {
  enterprise: "企业专线",
  hybrid_cloud: "混合云接入",
  public_cloud: "公有云接入",
  internal: "内部业务",
};
const STATUS_COLOR: Record<string, string> = {
  active: "green",
  suspended: "orange",
  terminated: "red",
};

interface TenantSummary {
  tenant_id: number;
  circuits_total: number;
  circuits_active: number;
  circuits_decommissioned: number;
  active_bandwidth_mbps: number;
}

export default function Tenants() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Tenant[]>([]);
  const [summaries, setSummaries] = useState<TenantSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    setLoading(true);
    try {
      const [t, s] = await Promise.all([
        api.get<Tenant[]>("/tenants"),
        api.get<TenantSummary[]>("/tenants/summaries"),
      ]);
      setRows(t.data);
      setSummaries(s.data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  function summaryOf(id: number) {
    return summaries.find((s) => s.tenant_id === id);
  }

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post("/tenants", values);
      message.success(toast.created);
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  async function remove(id: number) {
    await api.delete(`/tenants/${id}`);
    message.success(toast.deleted);
    load();
  }

  return (
    <Card
      title={page.tenants}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新建租户
        </Button>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        columns={[
          { title: "编码", dataIndex: "code" },
          { title: "名称", dataIndex: "name" },
          {
            title: "类型",
            dataIndex: "type",
            render: (t) => <Tag color="blue">{TYPE_LABEL[t] || t}</Tag>,
          },
          {
            title: "状态",
            dataIndex: "status",
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "专线",
            render: (_, r) => {
              const s = summaryOf(r.id);
              if (!s) return "-";
              return (
                <Space size={4}>
                  <Tag color="green">{s.circuits_active} 在网</Tag>
                  {s.circuits_decommissioned > 0 && (
                    <Tag>{s.circuits_decommissioned} 已下线</Tag>
                  )}
                  <span style={{ color: "#888", fontSize: 12 }}>
                    {s.active_bandwidth_mbps} Mbps
                  </span>
                </Space>
              );
            },
          },
          { title: "联系人", dataIndex: "contact_name" },
          { title: "云账号", dataIndex: "cloud_account" },
          {
            title: "操作",
            render: (_, r) => (
              <Space>
                <Link to={`/circuits?tenant=${r.id}`}>专线编排</Link>
                <Popconfirm title="确认删除该租户?" onConfirm={() => remove(r.id)}>
                  <a style={{ color: "#cf1322" }}>{action.delete}</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal title="新建租户" open={open} onOk={onCreate} onCancel={() => setOpen(false)} okText={action.create}>
        <Form form={form} layout="vertical" initialValues={{ type: "enterprise", status: "active" }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如 某金融集团" />
          </Form.Item>
          <Form.Item name="code" label="编码" rules={[{ required: true }]}>
            <Input placeholder="例如 BANK01" />
          </Form.Item>
          <Form.Item name="type" label="类型">
            <Select
              options={Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="contact_name" label="联系人">
            <Input />
          </Form.Item>
          <Form.Item name="cloud_account" label="云账号 (混合云接入)">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

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
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Paginated, Tenant } from "../api/types";
import { tablePagination } from "../utils/table";

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

export default function Tenants() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Tenant[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  async function load(p = page, ps = pageSize, q = search) {
    setLoading(true);
    try {
      const qs = new URLSearchParams({ page: String(p), page_size: String(ps) });
      if (q.trim()) qs.set("q", q.trim());
      const { data } = await api.get<Paginated<Tenant>>(`/tenants?${qs}`);
      setRows(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, pageSize]);

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post("/tenants", values);
      message.success("租户已创建");
      setOpen(false);
      form.resetFields();
      load(1);
      setPage(1);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function remove(id: number) {
    await api.delete(`/tenants/${id}`);
    message.success("已删除");
    load();
  }

  return (
    <Card
      title="客户服务"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新建客户
        </Button>
      }
    >
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          allowClear
          placeholder="搜索客户名称或编码"
          style={{ width: 300 }}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onSearch={() => {
            setPage(1);
            load(1, pageSize, search);
          }}
          enterButton={<SearchOutlined />}
        />
        <span style={{ color: "#888" }}>共 {total.toLocaleString()} 个客户</span>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        scroll={{ x: 960 }}
        pagination={tablePagination(total, page, pageSize, (p, ps) => {
          setPage(p);
          setPageSize(ps);
        })}
        columns={[
          { title: "名称", dataIndex: "name", width: 180, ellipsis: true },
          { title: "编码", dataIndex: "code", width: 120, render: (c) => <Tag>{c}</Tag> },
          {
            title: "类型",
            dataIndex: "type",
            width: 120,
            render: (t) => TYPE_LABEL[t] || t,
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 90,
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "专线数",
            dataIndex: "circuits_total",
            width: 90,
            render: (n) => n ?? 0,
          },
          { title: "联系人", dataIndex: "contact_name", width: 120, ellipsis: true },
          { title: "邮箱", dataIndex: "contact_email", ellipsis: true },
          {
            title: "操作",
            width: 160,
            fixed: "right",
            render: (_, r) => (
              <Space>
                <Link to={`/circuits?tenant=${r.id}`}>查看专线</Link>
                <Popconfirm title="确认删除?" onConfirm={() => remove(r.id)}>
                  <a style={{ color: "#cf1322" }}>删除</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal title="新建客户" open={open} onOk={onCreate} onCancel={() => setOpen(false)}>
        <Form form={form} layout="vertical" initialValues={{ type: "enterprise", status: "active" }}>
          <Form.Item name="name" label="客户名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label="编码" rules={[{ required: true }]}>
            <Input placeholder="例如 BANK-BJ" />
          </Form.Item>
          <Form.Item name="type" label="类型">
            <Select options={Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))} />
          </Form.Item>
          <Form.Item name="contact_name" label="联系人">
            <Input />
          </Form.Item>
          <Form.Item name="contact_email" label="邮箱">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

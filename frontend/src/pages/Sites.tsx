import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Table,
  Tag,
  App as AntApp,
  Popconfirm,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Site } from "../api/types";

export default function Sites() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    setLoading(true);
    try {
      const { data } = await api.get<Site[]>("/sites");
      setRows(data);
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
      await api.post("/sites", values);
      message.success("数据中心已创建");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function remove(id: number) {
    await api.delete(`/sites/${id}`);
    message.success("已删除");
    load();
  }

  return (
    <Card
      title="数据中心 (DC / 站点)"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新建数据中心
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
          { title: "区域", dataIndex: "region" },
          { title: "BGP ASN", dataIndex: "bgp_asn", render: (v) => v && <Tag>{v}</Tag> },
          { title: "Underlay 网段", dataIndex: "underlay_prefix" },
          {
            title: "操作",
            render: (_, r) => (
              <Space>
                <Popconfirm title="确认删除?" onConfirm={() => remove(r.id)}>
                  <a style={{ color: "#cf1322" }}>删除</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal title="新建数据中心" open={open} onOk={onCreate} onCancel={() => setOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如 北京数据中心" />
          </Form.Item>
          <Form.Item name="code" label="编码" rules={[{ required: true }]}>
            <Input placeholder="例如 BJ-DC1" />
          </Form.Item>
          <Form.Item name="region" label="区域">
            <Input placeholder="例如 华北" />
          </Form.Item>
          <Form.Item name="bgp_asn" label="BGP ASN">
            <InputNumber style={{ width: "100%" }} placeholder="例如 65001" />
          </Form.Item>
          <Form.Item name="underlay_prefix" label="Underlay 网段">
            <Input placeholder="例如 10.1.0.0/16" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

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
import { Select } from "antd";
import { api } from "../api/client";
import type { Controller, Site } from "../api/types";
import PageCard from "../components/PageCard";
import { dataTableProps } from "../utils/table";
import { formModalProps } from "../utils/formModal";
import { action, page, toast } from "../constants/uiCopy";

export default function Sites() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Site[]>([]);
  const [controllers, setControllers] = useState<Controller[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const deliveryMode = Form.useWatch("delivery_mode", form);

  async function load() {
    setLoading(true);
    try {
      const [s, c] = await Promise.all([
        api.get<Site[]>("/sites"),
        api.get<Controller[]>("/controllers"),
      ]);
      setRows(s.data);
      setControllers(c.data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  const controllerName = (id?: number) =>
    controllers.find((c) => c.id === id)?.name;

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post("/sites", values);
      message.success(toast.created);
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  async function remove(id: number) {
    await api.delete(`/sites/${id}`);
    message.success(toast.deleted);
    load();
  }

  return (
    <PageCard
      title={page.sites}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新建站点
        </Button>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        {...dataTableProps()}
        columns={[
          { title: "编码", dataIndex: "code", width: "10%", ellipsis: true },
          { title: "名称", dataIndex: "name", width: "14%", ellipsis: true },
          { title: "区域", dataIndex: "region", width: "10%", render: (v) => v || "—" },
          {
            title: "BGP ASN",
            dataIndex: "bgp_asn",
            width: "10%",
            render: (v) => (v ? <Tag>{v}</Tag> : "—"),
          },
          {
            title: "Underlay 网段",
            dataIndex: "underlay_prefix",
            width: "14%",
            ellipsis: true,
            render: (v) => v || "—",
          },
          {
            title: "下发模式",
            dataIndex: "delivery_mode",
            width: "18%",
            ellipsis: true,
            render: (m, r) =>
              m === "controller" ? (
                <Tag color="purple">控制器: {controllerName(r.controller_id) || "?"}</Tag>
              ) : (
                <Tag color="green">直连下发</Tag>
              ),
          },
          {
            title: "操作",
            width: "10%",
            className: "table-actions",
            render: (_, r) => (
              <Popconfirm title="确认删除该站点?" onConfirm={() => remove(r.id)}>
                <Button type="link" size="small" danger>
                  {action.delete}
                </Button>
              </Popconfirm>
            ),
          },
        ]}
      />
      <Modal
        title="新建 Fabric 站点"
        open={open}
        onOk={onCreate}
        onCancel={() => setOpen(false)}
        okText={action.create}
        {...formModalProps}
      >
        <Form form={form} layout="vertical" className="app-form">
          <Form.Item name="name" label="站点名称" rules={[{ required: true }]}>
            <Input placeholder="例如 北京 Fabric PoP" />
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
          <Form.Item name="delivery_mode" label="下发模式" initialValue="direct">
            <Select
              options={[
                { value: "direct", label: "直连下发 (NETCONF/CLI)" },
                { value: "controller", label: "控制器北向下发" },
              ]}
            />
          </Form.Item>
          {deliveryMode === "controller" && (
            <Form.Item name="controller_id" label="关联控制器" rules={[{ required: true }]}>
              <Select
                options={controllers.map((c) => ({
                  value: c.id,
                  label:
                    c.type === "bugis"
                      ? `${c.name} (内置 · 推荐)`
                      : c.name,
                }))}
              />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </PageCard>
  );
}

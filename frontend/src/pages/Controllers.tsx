import { useEffect, useState } from "react";
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
  Typography,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Controller } from "../api/types";

const TYPE_LABEL: Record<string, string> = {
  nce_fabric: "华为 NCE-Fabric",
  seerengine: "华三 SeerEngine",
  opendaylight: "OpenDaylight",
  onos: "ONOS",
};
const TYPE_COLOR: Record<string, string> = {
  nce_fabric: "red",
  seerengine: "blue",
  opendaylight: "orange",
  onos: "purple",
};

export default function Controllers() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Controller[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    setLoading(true);
    try {
      const { data } = await api.get<Controller[]>("/controllers");
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
      await api.post("/controllers", values);
      message.success("控制器已添加");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function remove(id: number) {
    await api.delete(`/controllers/${id}`);
    message.success("已删除");
    load();
  }

  return (
    <Card
      title="SDN / 厂商控制器"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          添加控制器
        </Button>
      }
    >
      <Typography.Paragraph type="secondary">
        控制器托管的数据中心，开通时由平台将业务意图通过北向 RESTful 下发给控制器，
        由控制器完成底层设备配置（厂商开放 API 路线）。在「数据中心」中将站点的下发模式设为
        <Tag>controller</Tag> 并关联控制器即可生效。
      </Typography.Paragraph>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        columns={[
          { title: "名称", dataIndex: "name" },
          {
            title: "类型",
            dataIndex: "type",
            render: (t) => <Tag color={TYPE_COLOR[t]}>{TYPE_LABEL[t] || t}</Tag>,
          },
          { title: "北向地址", dataIndex: "base_url" },
          { title: "账号", dataIndex: "username" },
          { title: "描述", dataIndex: "description" },
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
      <Modal title="添加控制器" open={open} onOk={onCreate} onCancel={() => setOpen(false)}>
        <Form form={form} layout="vertical" initialValues={{ type: "nce_fabric" }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如 华为 iMaster NCE-Fabric" />
          </Form.Item>
          <Form.Item name="type" label="类型">
            <Select
              options={Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="base_url" label="北向地址" rules={[{ required: true }]}>
            <Input placeholder="https://nce.example.com" />
          </Form.Item>
          <Space style={{ display: "flex" }}>
            <Form.Item name="username" label="账号" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="password" label="密码" style={{ flex: 1 }}>
              <Input.Password />
            </Form.Item>
          </Space>
          <Form.Item name="description" label="描述">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

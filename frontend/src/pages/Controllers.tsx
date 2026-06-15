import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert,
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
import { PlusOutlined, ShareAltOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Controller } from "../api/types";

const TYPE_LABEL: Record<string, string> = {
  bugis: "Bugis SDN 控制器 (内置)",
  nce_fabric: "华为 NCE-Fabric",
  seerengine: "华三 SeerEngine",
  opendaylight: "OpenDaylight",
  onos: "ONOS",
};
const TYPE_COLOR: Record<string, string> = {
  bugis: "geekblue",
  nce_fabric: "red",
  seerengine: "blue",
  opendaylight: "orange",
  onos: "purple",
};

const EXTERNAL_TYPES = Object.entries(TYPE_LABEL).filter(([value]) => value !== "bugis");

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
    if (values.type === "bugis") {
      return message.error("Bugis SDN 控制器为内置组件，无需手动添加");
    }
    try {
      await api.post("/controllers", values);
      message.success("外部控制器已添加");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function remove(id: number) {
    const ctrl = rows.find((r) => r.id === id);
    if (ctrl?.type === "bugis") {
      return message.error("内置 Bugis SDN 控制器不可删除");
    }
    try {
      await api.delete(`/controllers/${id}`);
      message.success("已删除");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "删除失败");
    }
  }

  const builtin = rows.find((r) => r.type === "bugis");
  const external = rows.filter((r) => r.type !== "bugis");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Alert
        type="info"
        showIcon
        icon={<ShareAltOutlined />}
        message="内置 vs 外部控制器"
        description={
          <span>
            <Tag color="geekblue">Bugis SDN 控制器</Tag> 是平台内嵌的自研 EVPN
            控制平面，应用启动时自动注册，<strong>不需要也不允许手动添加</strong>。
            在「数据中心」将下发模式设为「控制器托管」并选择内置控制器即可；控制面状态、版本与
            EVPN RIB 请查看{" "}
            <Link to="/control-plane">SDN 控制平面</Link> 页面。下方「添加外部控制器」用于对接
            华为 NCE-Fabric、华三 SeerEngine 等厂商/开源控制器。
          </span>
        }
      />

      <Card title="内置控制器">
        <Table
          rowKey="id"
          loading={loading}
          dataSource={builtin ? [builtin] : []}
          pagination={false}
          locale={{ emptyText: "内置控制器加载中…" }}
          columns={[
            { title: "名称", dataIndex: "name" },
            {
              title: "类型",
              dataIndex: "type",
              render: (t) => <Tag color={TYPE_COLOR[t]}>{TYPE_LABEL[t] || t}</Tag>,
            },
            {
              title: "北向地址",
              dataIndex: "base_url",
              render: (url) => (
                <Typography.Text code copyable>
                  {url}
                </Typography.Text>
              ),
            },
            {
              title: "说明",
              dataIndex: "description",
              render: (d) => d || "平台内置，自动注册",
            },
            {
              title: "操作",
              render: () => (
                <Link to="/control-plane">
                  <ShareAltOutlined /> 查看控制平面
                </Link>
              ),
            },
          ]}
        />
      </Card>

      <Card
        title="外部控制器"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            添加外部控制器
          </Button>
        }
      >
        <Typography.Paragraph type="secondary">
          控制器托管的数据中心，开通时由平台将业务意图通过北向 RESTful 下发给外部控制器，
          由控制器完成底层设备配置（厂商开放 API 路线）。
        </Typography.Paragraph>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={external}
          locale={{ emptyText: "暂无外部控制器" }}
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
      </Card>

      <Modal title="添加外部控制器" open={open} onOk={onCreate} onCancel={() => setOpen(false)}>
        <Form form={form} layout="vertical" initialValues={{ type: "nce_fabric" }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如 华为 iMaster NCE-Fabric" />
          </Form.Item>
          <Form.Item name="type" label="类型">
            <Select options={EXTERNAL_TYPES.map(([value, label]) => ({ value, label }))} />
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
    </div>
  );
}

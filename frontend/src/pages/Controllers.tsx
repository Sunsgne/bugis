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
import { action, empty, page, toast } from "../constants/uiCopy";
import PageCard from "../components/PageCard";
import { dataTableProps } from "../utils/table";

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
      return message.error("内置 Bugis SDN 控制器 · 无需手动纳管");
    }
    try {
      await api.post("/controllers", values);
      message.success("外部控制器已纳管");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  async function remove(id: number) {
    const ctrl = rows.find((r) => r.id === id);
    if (ctrl?.type === "bugis") {
      return message.error("内置控制器不可移除");
    }
    try {
      await api.delete(`/controllers/${id}`);
      message.success(toast.deleted);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
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
        message="内置 vs 北向控制器"
        description={
          <span>
            <Tag color="geekblue">Bugis SDN 控制器</Tag> 为平台内嵌自研 EVPN 控制平面，启动时自动注册，<strong>无需手动纳管</strong>。
            在 Fabric 站点将下发模式设为「控制器托管」并选择内置实例；控制面状态与 EVPN RIB 请前往{" "}
            <Link to="/control-plane">{page.controlPlane}</Link>。下方「纳管外部控制器」用于对接
            华为 NCE-Fabric、华三 SeerEngine 等厂商 / 开源控制器。
          </span>
        }
      />

      <PageCard title="内置控制器">
        <Table
          rowKey="id"
          loading={loading}
          dataSource={builtin ? [builtin] : []}
          pagination={false}
          locale={{ emptyText: empty.data }}
          {...dataTableProps()}
          columns={[
            { title: "名称", dataIndex: "name", width: "14%", ellipsis: true },
            {
              title: "类型",
              dataIndex: "type",
              width: "18%",
              render: (t) => <Tag color={TYPE_COLOR[t]}>{TYPE_LABEL[t] || t}</Tag>,
            },
            {
              title: "北向地址",
              dataIndex: "base_url",
              width: "28%",
              ellipsis: true,
              render: (url) => (
                <Typography.Text code copyable>
                  {url}
                </Typography.Text>
              ),
            },
            {
              title: "说明",
              dataIndex: "description",
              width: "28%",
              ellipsis: true,
              render: (d) => d || "平台内置 · 自动注册",
            },
            {
              title: "操作",
              width: "12%",
              className: "table-actions",
              render: () => (
                <Link to="/control-plane">
                  <ShareAltOutlined /> 进入控制面
                </Link>
              ),
            },
          ]}
        />
      </PageCard>

      <PageCard
        title="北向控制器"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            纳管外部控制器
          </Button>
        }
      >
        <Typography.Paragraph type="secondary">
          控制器托管模式下，平台将业务意图经北向 RESTful 下发至外部控制器，由后者完成底层设备编排。
        </Typography.Paragraph>
        <Table
          rowKey="id"
          loading={loading}
          dataSource={external}
          locale={{ emptyText: empty.default }}
          {...dataTableProps()}
          columns={[
            { title: "名称", dataIndex: "name", width: "16%", ellipsis: true },
            {
              title: "类型",
              dataIndex: "type",
              width: "18%",
              render: (t) => <Tag color={TYPE_COLOR[t]}>{TYPE_LABEL[t] || t}</Tag>,
            },
            { title: "北向地址", dataIndex: "base_url", width: "24%", ellipsis: true },
            { title: "账号", dataIndex: "username", width: "12%", ellipsis: true, render: (v) => v || "—" },
            { title: "描述", dataIndex: "description", width: "22%", ellipsis: true, render: (v) => v || "—" },
            {
              title: "操作",
              width: "8%",
              className: "table-actions",
              render: (_, r) => (
                <Popconfirm title={`${action.confirm}${action.delete}？`} onConfirm={() => remove(r.id)}>
                  <Button type="link" size="small" danger>
                    {action.delete}
                  </Button>
                </Popconfirm>
              ),
            },
          ]}
        />
      </PageCard>

      <Modal title="纳管外部控制器" open={open} onOk={onCreate} onCancel={() => setOpen(false)}>
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

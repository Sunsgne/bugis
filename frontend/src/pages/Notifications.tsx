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
import { PlusOutlined, SendOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import { action, page, toast } from "../constants/uiCopy";

interface Channel {
  id: number;
  name: string;
  type: string;
  url: string;
  min_severity: string;
  active: boolean;
  last_status?: string;
  last_dispatch_at?: string;
}

const TYPE_LABEL: Record<string, string> = {
  webhook: "通用 Webhook",
  dingtalk: "钉钉",
  wecom: "企业微信",
  feishu: "飞书 / Lark",
  slack: "Slack",
  teams: "Microsoft Teams",
  email: "邮件 (SMTP)",
};
const URL_HINT: Record<string, string> = {
  webhook: "https://your-endpoint/webhook",
  dingtalk: "https://oapi.dingtalk.com/robot/send?access_token=...",
  wecom: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...",
  feishu: "https://open.feishu.cn/open-apis/bot/v2/hook/...",
  slack: "https://hooks.slack.com/services/...",
  teams: "https://outlook.office.com/webhook/...",
  email: "收件人邮箱 noc@example.com",
};
const SEV_COLOR: Record<string, string> = {
  critical: "red",
  major: "volcano",
  minor: "orange",
  warning: "gold",
  info: "blue",
};

export default function Notifications() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const watchType = Form.useWatch("type", form);

  async function load() {
    setLoading(true);
    try {
      const { data } = await api.get<Channel[]>("/notifications");
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
      await api.post("/notifications", values);
      message.success(toast.created);
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  async function testSend(id: number) {
    const { data } = await api.post(`/notifications/${id}/test`);
    if (data.success) message.success("测试通知已送达");
    else message.error(`发送失败 · ${data.detail}`);
    load();
  }

  async function remove(id: number) {
    await api.delete(`/notifications/${id}`);
    message.success(toast.deleted);
    load();
  }

  return (
    <Card
      title={page.notifications}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新建渠道
        </Button>
      }
    >
      <Typography.Paragraph type="secondary">
        告警级别达到渠道阈值时，平台自动外发通知（Webhook · Slack · 钉钉 · 企业微信 · 飞书）。
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
            render: (t) => <Tag color="blue">{TYPE_LABEL[t] || t}</Tag>,
          },
          {
            title: "触发阈值",
            dataIndex: "min_severity",
            render: (s) => <Tag color={SEV_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "状态",
            dataIndex: "active",
            render: (a) => <Tag color={a ? "green" : "default"}>{a ? "启用" : "停用"}</Tag>,
          },
          { title: "最近结果", dataIndex: "last_status", ellipsis: true },
          {
            title: "最近发送",
            dataIndex: "last_dispatch_at",
            render: (t) => (t ? dayjs(t).format("MM-DD HH:mm:ss") : "-"),
          },
          {
            title: "操作",
            render: (_, r) => (
              <Space>
                <a onClick={() => testSend(r.id)}>
                  <SendOutlined /> 测试
                </a>
                <Popconfirm title={`${action.confirm}${action.delete}？`} onConfirm={() => remove(r.id)}>
                  <a style={{ color: "#cf1322" }}>{action.delete}</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal title="新建通知渠道" open={open} onOk={onCreate} onCancel={() => setOpen(false)}>
        <Form form={form} layout="vertical" initialValues={{ type: "dingtalk", min_severity: "major" }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="例如 NOC 运维群" />
          </Form.Item>
          <Form.Item name="type" label="类型">
            <Select options={Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))} />
          </Form.Item>
          <Form.Item
            name="url"
            label={watchType === "email" ? "收件人邮箱" : "Webhook 地址"}
            rules={[{ required: true }]}
          >
            <Input placeholder={URL_HINT[watchType] || "https://..."} />
          </Form.Item>
          <Form.Item name="min_severity" label="触发阈值 (达到该级别及以上发送)">
            <Select
              options={["critical", "major", "minor", "warning", "info"].map((v) => ({
                value: v,
                label: v,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

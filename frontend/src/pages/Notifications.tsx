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
      message.success("通知渠道已创建");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function testSend(id: number) {
    const { data } = await api.post(`/notifications/${id}/test`);
    if (data.success) message.success("测试通知已发送");
    else message.error(`发送失败: ${data.detail}`);
    load();
  }

  async function remove(id: number) {
    await api.delete(`/notifications/${id}`);
    message.success("已删除");
    load();
  }

  return (
    <Card
      title="告警通知渠道"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          添加渠道
        </Button>
      }
    >
      <Typography.Paragraph type="secondary">
        当告警级别达到渠道阈值时，平台自动向该渠道外发通知（支持通用 Webhook、Slack、钉钉、企业微信）。
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
                <Popconfirm title="确认删除?" onConfirm={() => remove(r.id)}>
                  <a style={{ color: "#cf1322" }}>删除</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal title="添加通知渠道" open={open} onOk={onCreate} onCancel={() => setOpen(false)}>
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

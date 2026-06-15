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
import PageCard from "../components/PageCard";
import { dataTableProps } from "../utils/table";
import { formModalProps } from "../utils/formModal";

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
const SEV_LABEL: Record<string, string> = {
  critical: "Critical 严重",
  major: "Major 重要",
  minor: "Minor 次要",
  warning: "Warning 警告",
  info: "Info 信息",
};
const SEV_COLOR: Record<string, string> = {
  critical: "red",
  major: "volcano",
  minor: "orange",
  warning: "gold",
  info: "blue",
};

export default function Notifications({ embedded }: { embedded?: boolean }) {
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
    if (data.success) message.success("测试通知已发送");
    else message.error(`发送失败 · ${data.detail}`);
    load();
  }

  async function remove(id: number) {
    await api.delete(`/notifications/${id}`);
    message.success(toast.deleted);
    load();
  }

  const addBtn = (
    <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
      新建渠道
    </Button>
  );

  const body = (
    <>
      <Typography.Paragraph type="secondary">
        告警级别达到渠道阈值时，平台自动外发通知（Webhook · Slack · 钉钉 · 企业微信 · 飞书）。
      </Typography.Paragraph>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        {...dataTableProps()}
        columns={[
          { title: "名称", dataIndex: "name", width: "14%", ellipsis: true },
          {
            title: "类型",
            dataIndex: "type",
            width: "14%",
            render: (t) => <Tag color="blue">{TYPE_LABEL[t] || t}</Tag>,
          },
          {
            title: "触发阈值",
            dataIndex: "min_severity",
            width: "10%",
            render: (s) => <Tag color={SEV_COLOR[s]}>{SEV_LABEL[s] || s}</Tag>,
          },
          {
            title: "状态",
            dataIndex: "active",
            width: "8%",
            render: (a) => <Tag color={a ? "green" : "default"}>{a ? "启用" : "停用"}</Tag>,
          },
          { title: "最近结果", dataIndex: "last_status", width: "18%", ellipsis: true, render: (v) => v || "—" },
          {
            title: "最近发送",
            dataIndex: "last_dispatch_at",
            width: "14%",
            render: (t) => (t ? dayjs(t).format("MM-DD HH:mm:ss") : "—"),
          },
          {
            title: "操作",
            width: "14%",
            className: "table-actions",
            render: (_, r) => (
              <Space size={4}>
                <Button type="link" size="small" icon={<SendOutlined />} onClick={() => testSend(r.id)}>
                  测试
                </Button>
                <Popconfirm title={`${action.confirm}${action.delete}？`} onConfirm={() => remove(r.id)}>
                  <Button type="link" size="small" danger>
                    {action.delete}
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal
        title="新建通知渠道"
        open={open}
        onOk={onCreate}
        onCancel={() => setOpen(false)}
        okText={action.create}
        {...formModalProps}
      >
        <Form form={form} layout="vertical" className="app-form" initialValues={{ type: "dingtalk", min_severity: "major" }}>
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
              options={Object.entries(SEV_LABEL).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );

  if (embedded) {
    return (
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <Typography.Title level={5} style={{ margin: 0 }}>
            {page.notifications}
          </Typography.Title>
          {addBtn}
        </div>
        {body}
      </div>
    );
  }

  return (
    <PageCard title={page.notifications} extra={addBtn}>
      {body}
    </PageCard>
  );
}

import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Table,
  Tag,
  App as AntApp,
  Alert,
  Typography,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { page, toast } from "../constants/uiCopy";
import PageCard from "../components/PageCard";
import { dataTableProps } from "../utils/table";

interface UserRow {
  id: number;
  username: string;
  full_name?: string;
  email?: string;
  role: string;
  is_active: boolean;
  created_at?: string;
}

const ROLE_COLOR: Record<string, string> = {
  admin: "red",
  operator: "blue",
  viewer: "default",
};

export default function Users({ embedded }: { embedded?: boolean }) {
  const { user } = useAuth();
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const isAdmin = user?.role === "admin";

  async function load() {
    if (!isAdmin) return;
    setLoading(true);
    try {
      const { data } = await api.get<UserRow[]>("/auth/users");
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
      await api.post("/auth/users", values);
      message.success(toast.created);
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  if (!isAdmin) {
    const denied = (
      <Alert type="warning" message="仅 Admin 角色可管理用户与权限" showIcon />
    );
    if (embedded) {
      return (
        <div>
          <Typography.Title level={5} style={{ marginTop: 0 }}>
            {page.users}
          </Typography.Title>
          {denied}
        </div>
      );
    }
    return <PageCard title={page.users}>{denied}</PageCard>;
  }

  const addBtn = (
    <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
      新建用户
    </Button>
  );

  const body = (
    <>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        {...dataTableProps()}
        columns={[
          { title: "用户名", dataIndex: "username", width: "14%", ellipsis: true },
          { title: "姓名", dataIndex: "full_name", width: "14%", ellipsis: true, render: (v) => v || "—" },
          { title: "邮箱", dataIndex: "email", width: "22%", ellipsis: true, render: (v) => v || "—" },
          {
            title: "角色",
            dataIndex: "role",
            width: "10%",
            render: (r) => <Tag color={ROLE_COLOR[r]}>{r}</Tag>,
          },
          {
            title: "状态",
            dataIndex: "is_active",
            width: "10%",
            render: (a) => <Tag color={a ? "green" : "default"}>{a ? "启用" : "禁用"}</Tag>,
          },
          {
            title: "创建时间",
            dataIndex: "created_at",
            width: "18%",
            render: (t) => (t ? dayjs(t).format("YYYY-MM-DD HH:mm") : "—"),
          },
        ]}
      />
      <Modal title="新建用户" open={open} onOk={onCreate} onCancel={() => setOpen(false)}>
        <Form form={form} layout="vertical" initialValues={{ role: "operator" }}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="full_name" label="姓名">
            <Input />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input />
          </Form.Item>
          <Form.Item name="role" label="角色">
            <Select
              options={[
                { value: "admin", label: "Admin 管理员" },
                { value: "operator", label: "Operator 操作员" },
                { value: "viewer", label: "Viewer 只读" },
              ]}
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
            {page.users} · RBAC
          </Typography.Title>
          {addBtn}
        </div>
        {body}
      </div>
    );
  }

  return (
    <PageCard title={`${page.users} · RBAC`} extra={addBtn}>
      {body}
    </PageCard>
  );
}

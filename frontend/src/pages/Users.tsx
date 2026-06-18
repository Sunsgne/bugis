import { useEffect, useState } from "react";
import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  App as AntApp,
  Alert,
  Typography,
} from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { action, page, toast } from "../constants/uiCopy";
import PageCard from "../components/PageCard";
import { dataTableProps } from "../utils/table";
import { formModalProps } from "../utils/formModal";
import { useTc } from "@/i18n/useTc";

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
  const { tc } = useTc();
  const { user } = useAuth();
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [editForm] = Form.useForm();

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

  function openEdit(row: UserRow) {
    setEditing(row);
    editForm.setFieldsValue({
      full_name: row.full_name,
      email: row.email,
      role: row.role,
      is_active: row.is_active,
      password: "",
    });
  }

  async function onEdit() {
    if (!editing) return;
    const values = await editForm.validateFields();
    const payload: Record<string, unknown> = {
      full_name: values.full_name || null,
      email: values.email || null,
      role: values.role,
      is_active: values.is_active,
    };
    if (values.password) payload.password = values.password;
    try {
      await api.patch(`/auth/users/${editing.id}`, payload);
      message.success(toast.saved);
      setEditing(null);
      editForm.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  async function onDelete(row: UserRow) {
    try {
      await api.delete(`/auth/users/${row.id}`);
      message.success(toast.deleted);
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
    <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>{tc('新建用户')}</Button>
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
            title: tc('角色'),
            dataIndex: "role",
            width: "10%",
            render: (r) => <Tag color={ROLE_COLOR[r]}>{r}</Tag>,
          },
          {
            title: tc('状态'),
            dataIndex: "is_active",
            width: "10%",
            render: (a) => <Tag color={a ? "green" : "default"}>{a ? "启用" : "禁用"}</Tag>,
          },
          {
            title: tc('创建时间'),
            dataIndex: "created_at",
            width: "16%",
            render: (t) => (t ? dayjs(t).format("YYYY-MM-DD HH:mm") : "—"),
          },
          {
            title: tc('操作'),
            key: "actions",
            width: "14%",
            render: (_: unknown, row: UserRow) => (
              <Space size="small">
                <Button
                  type="link"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => openEdit(row)}
                >
                  {action.edit}
                </Button>
                <Popconfirm
                  title={tc('删除用户')}
                  description={`确认删除用户 ${row.username}？此操作不可恢复。`}
                  okText={action.confirm}
                  cancelText={action.cancel}
                  okButtonProps={{ danger: true }}
                  disabled={row.id === user?.id}
                  onConfirm={() => onDelete(row)}
                >
                  <Button
                    type="link"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    disabled={row.id === user?.id}
                  >
                    {action.delete}
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal
        title={tc('编辑用户')}
        open={!!editing}
        onOk={onEdit}
        onCancel={() => {
          setEditing(null);
          editForm.resetFields();
        }}
        okText={action.save}
        {...formModalProps}
      >
        <Form form={editForm} layout="vertical" className="app-form">
          <Form.Item label={tc('用户名')}>
            <Input value={editing?.username} disabled />
          </Form.Item>
          <Form.Item name="full_name" label={tc('姓名')}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label={tc('邮箱')}>
            <Input />
          </Form.Item>
          <Form.Item name="role" label={tc('角色')}>
            <Select
              options={[
                { value: "admin", label: "Admin 管理员" },
                { value: "operator", label: "Operator 操作员" },
                { value: "viewer", label: "Viewer 只读" },
              ]}
            />
          </Form.Item>
          <Form.Item name="is_active" label={tc('状态')} valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
          <Form.Item
            name="password"
            label={tc('重置密码')}
            extra="留空则不修改；如需重置请输入至少 8 位新密码"
            rules={[{ min: 8, message: "新密码至少 8 位" }]}
          >
            <Input.Password autoComplete="new-password" placeholder={tc('留空不修改')} />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title={tc('新建用户')}
        open={open}
        onOk={onCreate}
        onCancel={() => setOpen(false)}
        okText={action.create}
        {...formModalProps}
      >
        <Form form={form} layout="vertical" className="app-form" initialValues={{ role: "operator" }}>
          <Form.Item name="username" label={tc('用户名')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label={tc('密码')} rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="full_name" label={tc('姓名')}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label={tc('邮箱')}>
            <Input />
          </Form.Item>
          <Form.Item name="role" label={tc('角色')}>
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

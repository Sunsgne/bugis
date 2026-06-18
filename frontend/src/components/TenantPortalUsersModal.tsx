import { useEffect, useState } from "react";
import { Button, Form, Input, Modal, Select, Space, Table, Tag, App as AntApp } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import { formModalProps } from "../utils/formModal";
import { useTc } from "@/i18n/useTc";

interface PortalUser {
  id: number;
  username: string;
  full_name?: string;
  email?: string;
  role: string;
  is_active: boolean;
}

interface Props {
  tenantId: number;
  tenantName: string;
  open: boolean;
  onClose: () => void;
}

export default function TenantPortalUsersModal({ tenantId, tenantName, open, onClose }: Props) {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [users, setUsers] = useState<PortalUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    setLoading(true);
    try {
      const { data } = await api.get<PortalUser[]>(`/tenants/${tenantId}/users`);
      setUsers(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (open) load();
  }, [open, tenantId]);

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post(`/tenants/${tenantId}/users`, values);
      message.success(tc('门户账号已创建'));
      setCreateOpen(false);
      form.resetFields();
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || "创建失败");
    }
  }

  async function onDelete(userId: number) {
    try {
      await api.delete(`/tenants/${tenantId}/users/${userId}`);
      message.success(tc('已删除'));
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || "删除失败");
    }
  }

  return (
    <>
      <Modal
        {...formModalProps}
        title={`客户门户账号 · ${tenantName}`}
        open={open}
        onCancel={onClose}
        footer={null}
        width={640}
      >
        <p style={{ color: "#666", marginBottom: 12 }}>{tc('客户使用此账号登录')}<strong>/portal</strong>{tc('，仅可查看本租户专线、流量与 95 计费数据。')}</p>
        <Space style={{ marginBottom: 12 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>{tc('新建门户账号')}</Button>
        </Space>
        <Table
          size="small"
          rowKey="id"
          loading={loading}
          dataSource={users}
          pagination={false}
          locale={{ emptyText: "暂无门户账号" }}
          columns={[
            { title: "用户名", dataIndex: "username" },
            { title: "姓名", dataIndex: "full_name", render: (v?: string) => v || "—" },
            {
              title: tc('角色'),
              dataIndex: "role",
              render: (r: string) => (
                <Tag color={r === "tenant_admin" ? "blue" : "default"}>
                  {r === "tenant_admin" ? "管理员" : "只读"}
                </Tag>
              ),
            },
            {
              title: tc('操作'),
              width: 80,
              render: (_: unknown, row: PortalUser) => (
                <Button type="link" danger size="small" onClick={() => onDelete(row.id)}>{tc('删除')}</Button>
              ),
            },
          ]}
        />
      </Modal>

      <Modal
        title={tc('新建门户账号')}
        open={createOpen}
        onOk={onCreate}
        onCancel={() => setCreateOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" initialValues={{ role: "tenant_viewer" }}>
          <Form.Item name="username" label={tc('登录用户名')} rules={[{ required: true, min: 3 }]}>
            <Input placeholder={tc('例如 acme_ops')} />
          </Form.Item>
          <Form.Item name="password" label={tc('初始密码')} rules={[{ required: true, min: 8 }]}>
            <Input.Password placeholder={tc('至少 8 位')} />
          </Form.Item>
          <Form.Item name="full_name" label={tc('显示名称')}>
            <Input placeholder={tc('可选')} />
          </Form.Item>
          <Form.Item name="email" label={tc('邮箱')}>
            <Input placeholder={tc('可选')} />
          </Form.Item>
          <Form.Item name="role" label={tc('角色')}>
            <Select
              options={[
                { value: "tenant_viewer", label: "只读 — 查看专线与流量" },
                { value: "tenant_admin", label: "管理员 — 可管理门户账号" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

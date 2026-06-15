import { useState } from "react";
import { App as AntApp, Form, Input, Modal } from "antd";
import { api } from "../api/client";
import { formModalProps } from "../utils/formModal";

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function ChangePasswordDialog({ open, onClose }: Props) {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  async function onOk() {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.post("/auth/change-password", {
        current_password: values.current_password,
        new_password: values.new_password,
      });
      message.success("密码已更新");
      form.resetFields();
      onClose();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "修改失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title="修改密码"
      open={open}
      onOk={onOk}
      onCancel={() => {
        form.resetFields();
        onClose();
      }}
      confirmLoading={saving}
      okText="保存"
      cancelText="取消"
      destroyOnClose
      {...formModalProps}
    >
      <Form form={form} layout="vertical" className="app-form">
        <Form.Item
          name="current_password"
          label="当前密码"
          rules={[{ required: true, message: "请输入当前密码" }]}
        >
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Form.Item
          name="new_password"
          label="新密码"
          rules={[
            { required: true, message: "请输入新密码" },
            { min: 8, message: "至少 8 位" },
          ]}
        >
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <Form.Item
          name="confirm_password"
          label="确认新密码"
          dependencies={["new_password"]}
          rules={[
            { required: true, message: "请再次输入新密码" },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue("new_password") === value) return Promise.resolve();
                return Promise.reject(new Error("两次输入不一致"));
              },
            }),
          ]}
        >
          <Input.Password autoComplete="new-password" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

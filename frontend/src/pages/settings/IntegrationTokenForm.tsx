import { Button, Form, Input, App as AntApp } from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";
import { useTc } from "@/i18n/useTc";

export default function IntegrationTokenForm() {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const { platform, loading, saving, save } = usePlatformSettings();

  useEffect(() => {
    if (platform) form.setFieldsValue({ webhook_token: platform.webhook_token });
  }, [platform, form]);

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save({ webhook_token: v.webhook_token });
      message.success(tc('Webhook Token 已保存'));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  return (
    <Form form={form} layout="inline" disabled={loading}>
      <Form.Item name="webhook_token" label="Webhook Token" rules={[{ required: true }]}>
        <Input.Password style={{ width: 320 }} placeholder="X-Webhook-Token" />
      </Form.Item>
      <Form.Item>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>{tc('保存')}</Button>
      </Form.Item>
    </Form>
  );
}

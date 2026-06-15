import { Button, Col, Form, Input, InputNumber, Row, Space, App as AntApp, Typography } from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";

export default function SmtpSettings() {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const { platform, loading, saving, save } = usePlatformSettings();

  useEffect(() => {
    if (platform) form.setFieldsValue(platform);
  }, [platform, form]);

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save({
        smtp_host: v.smtp_host,
        smtp_port: v.smtp_port,
        smtp_user: v.smtp_user,
        smtp_from: v.smtp_from,
        ...(v.smtp_password ? { smtp_password: v.smtp_password } : {}),
      });
      message.success("SMTP 参数已保存");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            邮件 SMTP
          </Typography.Title>
          <Typography.Text type="secondary">告警邮件通知渠道使用</Typography.Text>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>
          保存
        </Button>
      </Space>
      <Form form={form} layout="vertical" disabled={loading}>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="smtp_host" label="SMTP 主机">
              <Input placeholder="smtp.example.com" />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item name="smtp_port" label="端口">
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item name="smtp_from" label="发件人">
              <Input placeholder="noc@example.com" />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="smtp_user" label="用户名">
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="smtp_password"
              label="密码"
              extra={platform?.smtp_password_set ? "已设置，留空则不修改" : undefined}
            >
              <Input.Password placeholder="留空保持原值" autoComplete="new-password" />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </div>
  );
}

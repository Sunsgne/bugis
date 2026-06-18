import {
  Alert,
  Button,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  App as AntApp,
  Typography,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";
import { useTc } from "@/i18n/useTc";
import {
  SMTP_CATEGORIES,
  SMTP_PRESETS,
  SMTP_SECURITY_OPTIONS,
  getSmtpPreset,
  guessSmtpProvider,
} from "../../data/smtpPresets";

export default function SmtpSettings() {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const { platform, loading, saving, save } = usePlatformSettings();
  const [providerId, setProviderId] = useState("custom");

  const preset = useMemo(() => getSmtpPreset(providerId), [providerId]);

  useEffect(() => {
    if (!platform) return;
    const guessed = platform.smtp_provider || guessSmtpProvider(platform.smtp_host, platform.smtp_port);
    setProviderId(guessed);
    form.setFieldsValue({
      ...platform,
      smtp_provider: guessed,
      smtp_security: platform.smtp_security || "starttls",
    });
  }, [platform, form]);

  function applyPreset(id: string) {
    setProviderId(id);
    const p = getSmtpPreset(id);
    if (!p || id === "custom") {
      form.setFieldValue("smtp_provider", "custom");
      return;
    }
    form.setFieldsValue({
      smtp_provider: id,
      smtp_host: p.host,
      smtp_port: p.port,
      smtp_security: p.security,
    });
  }

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save({
        smtp_provider: v.smtp_provider || providerId,
        smtp_security: v.smtp_security,
        smtp_host: v.smtp_host,
        smtp_port: v.smtp_port,
        smtp_user: v.smtp_user,
        smtp_from: v.smtp_from,
        ...(v.smtp_password ? { smtp_password: v.smtp_password } : {}),
      });
      message.success(tc('SMTP 参数已保存'));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  const groupedOptions = SMTP_CATEGORIES.map((cat) => ({
    label: cat,
    options: SMTP_PRESETS.filter((p) => p.category === cat).map((p) => ({
      value: p.id,
      label: p.name,
    })),
  }));

  return (
    <div className="settings-panel">
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>{tc('邮件 SMTP')}</Typography.Title>
          <Typography.Text type="secondary">{tc('告警「邮件」通知渠道使用；选择主流平台自动填充服务器参数')}</Typography.Text>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>{tc('保存')}</Button>
      </Space>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="支持主流邮件平台"
        description={tc('涵盖 QQ / 163 / 企业邮、Gmail / Outlook、SendGrid / Mailgun / AWS SES 等，选择后自动填入 SMTP 主机、端口与加密方式，仅需填写账号与授权码。')}
      />

      <Form form={form} layout="vertical" className="app-form" disabled={loading}>
        <Form.Item name="smtp_provider" label={tc('邮件平台')}>
          <Select
            showSearch
            optionFilterProp="label"
            options={groupedOptions}
            value={providerId}
            onChange={applyPreset}
            placeholder={tc('选择邮件服务商')}
          />
        </Form.Item>

        {preset?.doc && (
          <Alert type="warning" showIcon style={{ marginBottom: 16 }} message={preset.doc} />
        )}

        <Row gutter={16}>
          <Col xs={24} md={10}>
            <Form.Item name="smtp_host" label={tc('SMTP 主机')} rules={[{ required: true, message: "请输入 SMTP 主机" }]}>
              <Input placeholder="smtp.example.com" />
            </Form.Item>
          </Col>
          <Col xs={12} md={4}>
            <Form.Item name="smtp_port" label={tc('端口')} rules={[{ required: true }]}>
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={10}>
            <Form.Item name="smtp_security" label={tc('加密方式')}>
              <Select
                options={SMTP_SECURITY_OPTIONS}
                onChange={() => setProviderId("custom")}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="smtp_user"
              label={tc('用户名 / 账号')}
              extra={preset?.userHint}
            >
              <Input placeholder={preset?.userHint || "SMTP 登录账号"} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="smtp_password"
              label={tc('密码 / 授权码')}
              extra={platform?.smtp_password_set ? "已设置，留空则不修改" : "多数平台需使用授权码而非登录密码"}
            >
              <Input.Password placeholder={tc('留空保持原值')} autoComplete="new-password" />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="smtp_from" label={tc('发件人地址')} extra={preset?.fromHint}>
              <Input placeholder={preset?.fromHint || "noc@example.com"} />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </div>
  );
}

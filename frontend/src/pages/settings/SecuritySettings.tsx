import {
  Alert,
  Button,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  QRCode,
  Row,
  Space,
  Switch,
  App as AntApp,
  Typography,
  Divider,
  Tag,
} from "antd";
import { KeyOutlined, MailOutlined, SaveOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useAuth } from "../../auth";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";

const { Text, Paragraph } = Typography;

export default function SecuritySettings() {
  const { message } = AntApp.useApp();
  const { user, refreshUser } = useAuth();
  const [form] = Form.useForm();
  const { platform, loading, saving, save, load } = usePlatformSettings();
  const [totpUri, setTotpUri] = useState<string | null>(null);
  const [totpSecret, setTotpSecret] = useState<string | null>(null);
  const [confirmCode, setConfirmCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [disablePassword, setDisablePassword] = useState("");
  const [mfaBusy, setMfaBusy] = useState(false);

  useEffect(() => {
    if (platform) form.setFieldsValue(platform);
  }, [platform, form]);

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save(v);
      message.success("安全策略已保存");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  async function setupTotp() {
    setMfaBusy(true);
    try {
      const { data } = await api.get<{ secret: string; provisioning_uri: string }>(
        "/auth/mfa/totp/setup",
      );
      setTotpSecret(data.secret);
      setTotpUri(data.provisioning_uri);
      message.info("请使用验证器 App 扫描二维码或手动输入密钥");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "初始化失败");
    } finally {
      setMfaBusy(false);
    }
  }

  async function confirmTotp() {
    if (!confirmCode.trim()) return message.warning("请输入 6 位验证码");
    setMfaBusy(true);
    try {
      await api.post("/auth/mfa/totp/confirm", { code: confirmCode.trim() });
      message.success("验证器 MFA 已启用");
      setTotpUri(null);
      setTotpSecret(null);
      setConfirmCode("");
      await refreshUser();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "确认失败");
    } finally {
      setMfaBusy(false);
    }
  }

  async function disableMfa() {
    if (!disablePassword || !disableCode.trim()) {
      return message.warning("请输入密码与验证码");
    }
    setMfaBusy(true);
    try {
      await api.post("/auth/mfa/disable", {
        password: disablePassword,
        code: disableCode.trim(),
      });
      message.success("MFA 已关闭");
      setDisableCode("");
      setDisablePassword("");
      await refreshUser();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "关闭失败");
    } finally {
      setMfaBusy(false);
    }
  }

  return (
    <div className="settings-panel">
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            安全与认证
          </Typography.Title>
          <Text type="secondary">登录防护、Cloudflare Turnstile、双因素认证与 API 暴露策略</Text>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>
          保存策略
        </Button>
      </Space>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="建议在生产环境启用 Turnstile 或前置 Cloudflare WAF，并为管理员开启 TOTP 验证器。"
      />

      <Form form={form} layout="vertical" className="app-form" disabled={loading}>
        <Typography.Title level={5}>登录防护</Typography.Title>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item name="login_rate_limit_per_ip" label="同 IP 最大失败次数">
              <InputNumber min={5} max={500} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="login_rate_limit_window_minutes" label="统计窗口 (分钟)">
              <InputNumber min={1} max={120} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="captcha_after_failures" label="失败 N 次后要求人机验证">
              <InputNumber min={0} max={50} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="login_lockout_after_failures" label="账号锁定阈值">
              <InputNumber min={1} max={50} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="login_lockout_minutes" label="锁定时长 (分钟)">
              <InputNumber min={1} max={1440} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="expose_openapi" label="暴露 OpenAPI 文档 (/docs)" valuePropName="checked">
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
        </Row>

        <Divider />
        <Typography.Title level={5}>Cloudflare Turnstile</Typography.Title>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item name="turnstile_enabled" label="启用 Turnstile" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="turnstile_site_key" label="Site Key (公开)">
              <Input placeholder="0x4AAAA..." />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="turnstile_secret_key" label="Secret Key">
              <Input.Password placeholder={platform?.turnstile_secret_key_set ? "已设置，留空不修改" : ""} />
            </Form.Item>
          </Col>
        </Row>

        <Divider />
        <Typography.Title level={5}>双因素认证 (2FA)</Typography.Title>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item name="mfa_required_platform" label="强制平台账号 MFA" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="mfa_required_portal" label="强制门户账号 MFA" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
          <Col xs={24} md={4}>
            <Form.Item name="mfa_allow_totp" label="允许验证器" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
          <Col xs={24} md={4}>
            <Form.Item name="mfa_allow_email" label="允许邮件 OTP" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
        </Row>
      </Form>

      <Divider />
      <Typography.Title level={5}>
        <SafetyCertificateOutlined /> 我的账号 · {user?.username}
      </Typography.Title>
      <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
        <Descriptions.Item label="邮箱">{user?.email || "未配置"}</Descriptions.Item>
        <Descriptions.Item label="MFA 状态">
          {user?.mfa_enabled ? <Tag color="green">已启用</Tag> : <Tag>未启用</Tag>}
        </Descriptions.Item>
      </Descriptions>

      {!user?.mfa_enabled ? (
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            用 Google Authenticator、Microsoft Authenticator、1Password 等验证器 App
            扫描二维码（或手动输入密钥）添加账号，再输入 App 显示的 6 位验证码完成绑定。
          </Paragraph>
          {!totpUri ? (
            <Button type="primary" icon={<KeyOutlined />} loading={mfaBusy} onClick={setupTotp}>
              生成验证器二维码
            </Button>
          ) : (
            <>
              <div className="mfa-setup-grid">
                <div className="mfa-qr">
                  <QRCode value={totpUri} size={176} errorLevel="M" />
                </div>
                <Space direction="vertical" size={10} style={{ minWidth: 220, flex: 1 }}>
                  <Text strong>1. 扫描左侧二维码</Text>
                  <Text type="secondary" style={{ marginBottom: 4 }}>
                    无法扫描？在 App 中手动添加（类型选「基于时间 TOTP」），密钥：
                  </Text>
                  {totpSecret && (
                    <Text code copyable={{ text: totpSecret }} style={{ fontSize: 14, wordBreak: "break-all" }}>
                      {totpSecret}
                    </Text>
                  )}
                  <Text strong style={{ marginTop: 8 }}>2. 输入 App 生成的 6 位验证码</Text>
                  <Space.Compact style={{ width: "100%", maxWidth: 280 }}>
                    <Input
                      placeholder="6 位验证码"
                      value={confirmCode}
                      onChange={(e) => setConfirmCode(e.target.value)}
                      maxLength={6}
                      inputMode="numeric"
                      onPressEnter={confirmTotp}
                    />
                    <Button type="primary" loading={mfaBusy} onClick={confirmTotp}>
                      确认启用
                    </Button>
                  </Space.Compact>
                </Space>
              </div>
            </>
          )}
        </Space>
      ) : (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input.Password
            placeholder="当前密码"
            value={disablePassword}
            onChange={(e) => setDisablePassword(e.target.value)}
            style={{ maxWidth: 280 }}
          />
          <Space>
            <Input
              placeholder="验证码"
              value={disableCode}
              onChange={(e) => setDisableCode(e.target.value)}
              style={{ width: 160 }}
            />
            <Button danger loading={mfaBusy} onClick={disableMfa}>
              关闭 MFA
            </Button>
          </Space>
        </Space>
      )}

      {user?.email && (
        <Paragraph type="secondary" style={{ marginTop: 12 }}>
          <MailOutlined /> 邮件 OTP 需在登录第二步选择「发送邮件验证码」（需先配置 SMTP）。
        </Paragraph>
      )}
    </div>
  );
}

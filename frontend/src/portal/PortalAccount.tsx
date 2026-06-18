import { useEffect, useState } from "react";
import {
  App as AntApp,
  Button,
  Card,
  Descriptions,
  Divider,
  Form,
  Input,
  QRCode,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  KeyOutlined,
  MailOutlined,
  SafetyCertificateOutlined,
  SaveOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { useAuth } from "../auth";
import UserPreferencesCard from "../components/UserPreferencesCard";

const { Text, Paragraph, Title } = Typography;

export default function PortalAccount() {
  const { message } = AntApp.useApp();
  const { t } = useTranslation();
  const { user, refreshUser } = useAuth();
  const [profileForm] = Form.useForm();
  const [pwdForm] = Form.useForm();
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPwd, setSavingPwd] = useState(false);

  const [totpUri, setTotpUri] = useState<string | null>(null);
  const [totpSecret, setTotpSecret] = useState<string | null>(null);
  const [confirmCode, setConfirmCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [disablePassword, setDisablePassword] = useState("");
  const [mfaBusy, setMfaBusy] = useState(false);

  useEffect(() => {
    if (user) {
      profileForm.setFieldsValue({ full_name: user.full_name, email: user.email });
    }
  }, [user, profileForm]);

  async function saveProfile() {
    const v = await profileForm.validateFields();
    setSavingProfile(true);
    try {
      await api.patch("/auth/profile", {
        full_name: v.full_name || null,
        email: v.email || null,
      });
      message.success(t("account.profileSaved"));
      await refreshUser();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    } finally {
      setSavingProfile(false);
    }
  }

  async function changePassword() {
    const v = await pwdForm.validateFields();
    setSavingPwd(true);
    try {
      await api.post("/auth/change-password", {
        current_password: v.current_password,
        new_password: v.new_password,
      });
      message.success("密码已更新");
      pwdForm.resetFields();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "修改失败");
    } finally {
      setSavingPwd(false);
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
      message.success("双因素认证已启用");
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
      return message.warning("请输入登录密码与验证码");
    }
    setMfaBusy(true);
    try {
      await api.post("/auth/mfa/disable", {
        password: disablePassword,
        code: disableCode.trim(),
      });
      message.success("双因素认证已关闭");
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
    <Space direction="vertical" size={20} style={{ width: "100%", maxWidth: 880 }}>
      <UserPreferencesCard />

      <Card
        title={
          <Space>
            <UserOutlined />
            {t("account.profile")}
          </Space>
        }
        styles={{ header: { borderBottom: "1px solid #f0f0f0" } }}
      >
        <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
          <Descriptions.Item label={t("account.username")}>{user?.username}</Descriptions.Item>
          <Descriptions.Item label={t("account.role")}>
            <Tag color="blue">
              {user?.role === "tenant_admin" ? t("portal.roleTenantAdmin") : t("portal.roleTenantViewer")}
            </Tag>
          </Descriptions.Item>
        </Descriptions>
        <Form form={profileForm} layout="vertical" style={{ maxWidth: 420 }}>
          <Form.Item name="full_name" label={t("account.fullName")}>
            <Input placeholder={t("account.fullNamePlaceholder")} maxLength={128} />
          </Form.Item>
          <Form.Item
            name="email"
            label={t("account.email")}
            tooltip={t("account.emailTooltip")}
            rules={[{ type: "email", message: t("account.emailPlaceholder") }]}
          >
            <Input placeholder={t("account.emailPlaceholder")} maxLength={255} />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} loading={savingProfile} onClick={saveProfile}>
            {t("account.saveProfile")}
          </Button>
        </Form>
      </Card>

      <Card
        title={
          <Space>
            <KeyOutlined />
            修改密码
          </Space>
        }
        styles={{ header: { borderBottom: "1px solid #f0f0f0" } }}
      >
        <Form form={pwdForm} layout="vertical" style={{ maxWidth: 420 }}>
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
          <Button type="primary" loading={savingPwd} onClick={changePassword}>
            更新密码
          </Button>
        </Form>
      </Card>

      <Card
        title={
          <Space>
            <SafetyCertificateOutlined />
            双因素认证 (2FA)
          </Space>
        }
        extra={user?.mfa_enabled ? <Tag color="green">已启用</Tag> : <Tag>未启用</Tag>}
        styles={{ header: { borderBottom: "1px solid #f0f0f0" } }}
      >
        {!user?.mfa_enabled ? (
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              使用 Google Authenticator、Microsoft Authenticator、1Password 等验证器 App
              扫描二维码（或手动输入密钥）添加账号，再输入 App 显示的 6 位验证码完成绑定。开启后登录将更安全。
            </Paragraph>
            {!totpUri ? (
              <Button type="primary" icon={<KeyOutlined />} loading={mfaBusy} onClick={setupTotp}>
                生成验证器二维码
              </Button>
            ) : (
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
                  <Text strong style={{ marginTop: 8 }}>
                    2. 输入 App 生成的 6 位验证码
                  </Text>
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
            )}
          </Space>
        ) : (
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              你的账号已开启双因素认证。如需关闭，请输入登录密码与当前验证器的 6 位验证码。
            </Paragraph>
            <Input.Password
              placeholder="当前登录密码"
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
                关闭 2FA
              </Button>
            </Space>
          </Space>
        )}

        {user?.email ? (
          <>
            <Divider />
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              <MailOutlined /> 已绑定邮箱 {user.email}，登录第二步可选择「发送邮件验证码」获取一次性验证码。
            </Paragraph>
          </>
        ) : (
          <>
            <Divider />
            <Paragraph type="warning" style={{ marginBottom: 0 }}>
              <MailOutlined /> 你尚未绑定邮箱，无法使用邮件验证码与密码找回功能，建议在上方「账号资料」中补充邮箱。
            </Paragraph>
          </>
        )}
      </Card>
    </Space>
  );
}

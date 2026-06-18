import { useEffect, useState } from "react";
import { App as AntApp, Button, Card, Descriptions, Form, Input, Space, Tag } from "antd";
import { KeyOutlined, SaveOutlined, UserOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { useAuth } from "../auth";
import ChangePasswordDialog from "../components/ChangePasswordDialog";
import UserPreferencesCard from "../components/UserPreferencesCard";

export default function AccountSettings() {
  const { message } = AntApp.useApp();
  const { t } = useTranslation();
  const { user, refreshUser } = useAuth();
  const [profileForm] = Form.useForm();
  const [savingProfile, setSavingProfile] = useState(false);
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);

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
      message.error(e?.response?.data?.detail || t("account.saveFailed"));
    } finally {
      setSavingProfile(false);
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
            <Tag color="blue">{user?.role}</Tag>
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
            {t("action.changePassword")}
          </Space>
        }
        styles={{ header: { borderBottom: "1px solid #f0f0f0" } }}
      >
        <Button type="primary" onClick={() => setChangePasswordOpen(true)}>
          {t("action.changePassword")}
        </Button>
        <ChangePasswordDialog open={changePasswordOpen} onClose={() => setChangePasswordOpen(false)} />
      </Card>
    </Space>
  );
}

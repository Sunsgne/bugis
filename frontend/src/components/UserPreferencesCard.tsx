import { useEffect, useState } from "react";
import { App as AntApp, Button, Card, Form, Select, Space, Typography } from "antd";
import { GlobalOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { TIMEZONE_OPTIONS } from "../constants/timezones";
import { useLocale } from "../context/LocaleContext";

export default function UserPreferencesCard() {
  const { message } = AntApp.useApp();
  const { t } = useTranslation();
  const { locale, timezone, savePreferences } = useLocale();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    form.setFieldsValue({ locale, timezone });
  }, [form, locale, timezone]);

  async function onSave() {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await savePreferences({ locale: values.locale, timezone: values.timezone });
      message.success(t("account.preferencesSaved"));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t("account.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  const tzOptions = TIMEZONE_OPTIONS.map((opt) => ({
    value: opt.value,
    label: locale === "zh" ? opt.labelZh : opt.labelEn,
  }));

  return (
    <Card
      title={
        <Space>
          <GlobalOutlined />
          {t("account.preferences")}
        </Space>
      }
      styles={{ header: { borderBottom: "1px solid #f0f0f0" } }}
    >
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        {t("account.timezoneHint")}
      </Typography.Paragraph>
      <Form form={form} layout="vertical" style={{ maxWidth: 420 }}>
        <Form.Item name="locale" label={t("account.language")}>
          <Select
            options={[
              { value: "zh", label: t("account.languageZh") },
              { value: "en", label: t("account.languageEn") },
            ]}
          />
        </Form.Item>
        <Form.Item name="timezone" label={t("account.timezone")}>
          <Select
            showSearch
            optionFilterProp="label"
            options={tzOptions}
          />
        </Form.Item>
        <Form.Item>
          <Button type="primary" loading={saving} onClick={onSave}>
            {t("action.save")}
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}

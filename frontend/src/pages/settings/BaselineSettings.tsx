import { Alert, Button, Form, Input, Space, App as AntApp, Typography } from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";

export default function BaselineSettings() {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const { platform, loading, saving, save } = usePlatformSettings();

  useEffect(() => {
    if (platform) {
      form.setFieldsValue({
        baseline_ntp_server: platform.baseline_ntp_server,
        baseline_syslog_server: platform.baseline_syslog_server,
      });
    }
  }, [platform, form]);

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save(v);
      message.success("设备基线参数已保存");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            设备基线
          </Typography.Title>
          <Typography.Text type="secondary">写入设备初始化模板的 NTP / Syslog</Typography.Text>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>
          保存
        </Button>
      </Space>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="SNMP community 请在「SNMP 采集」页配置 baseline_community。"
      />
      <Form form={form} layout="vertical" disabled={loading} style={{ maxWidth: 480 }}>
        <Form.Item name="baseline_ntp_server" label="NTP 服务器">
          <Input placeholder="10.0.0.1" />
        </Form.Item>
        <Form.Item name="baseline_syslog_server" label="Syslog 服务器">
          <Input placeholder="10.0.0.2" />
        </Form.Item>
      </Form>
    </div>
  );
}

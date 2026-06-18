import {
  Alert,
  Button,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Space,
  Typography,
  App as AntApp,
} from "antd";
import { Link } from "react-router-dom";
import { SaveOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";
import { useTc } from "@/i18n/useTc";

const { Text } = Typography;

export default function ManagementSettings() {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const { platform, loading, saving, save } = usePlatformSettings();

  useEffect(() => {
    if (platform) {
      form.setFieldsValue({
        default_netconf_port: platform.default_netconf_port ?? 830,
        default_ssh_port: platform.default_ssh_port ?? 22,
        default_username: platform.default_username ?? "admin",
        netconf_timeout: platform.netconf_timeout ?? 30,
        ssh_timeout: platform.ssh_timeout ?? 30,
      });
    }
  }, [platform, form]);

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save(v);
      message.success(tc('南向接口默认参数已保存'));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  return (
    <div className="settings-panel">
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>{tc('南向接口')}</Typography.Title>
          <Text type="secondary">{tc('NETCONF / SSH 默认端口、账号与超时；纳管新设备时自动填充')}</Text>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>{tc('保存')}</Button>
      </Space>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="SNMP 采集"
        description={
          <>
            SNMP Community、v3 认证与 IF-MIB 采集策略请在{" "}
            <Link to="/settings/snmp">{tc('SNMP 采集')}</Link>{tc('页面配置；单台设备可在「设备管理 → 凭证」中覆盖。')}</>
        }
      />

      <Form form={form} layout="vertical" className="app-form" disabled={loading}>
        <Row gutter={16}>
          <Col xs={12} md={6}>
            <Form.Item name="default_netconf_port" label={tc('默认 NETCONF 端口')}>
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="default_ssh_port" label={tc('默认 SSH 端口')}>
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="default_username" label={tc('默认用户名')}>
              <Input placeholder="admin / netconf" />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={12} md={6}>
            <Form.Item name="netconf_timeout" label={tc('NETCONF 超时 (秒)')}>
              <InputNumber min={5} max={300} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="ssh_timeout" label={tc('SSH 超时 (秒)')}>
              <InputNumber min={5} max={300} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </div>
  );
}

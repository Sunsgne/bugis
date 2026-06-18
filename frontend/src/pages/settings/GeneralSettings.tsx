import {
  Alert,
  Button,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Row,
  Space,
  Switch,
  App as AntApp,
  Typography,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";
import { useAuth } from "../../auth";

const { Text } = Typography;

export default function GeneralSettings() {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const { platform, readonly, loading, saving, save } = usePlatformSettings();
  const { user } = useAuth();
  const canEdit = user?.role === "admin" || user?.role === "operator";

  useEffect(() => {
    if (platform) form.setFieldsValue(platform);
  }, [platform, form]);

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save(v);
      message.success("平台运行参数已保存");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  return (
    <div className="settings-panel">
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            平台运行
          </Typography.Title>
          <Text type="secondary">下发模式、调度器、控制器与认证相关参数</Text>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave} disabled={!canEdit}>
          保存
        </Button>
      </Space>

      {!canEdit && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="只读：当前账号无修改平台运行参数的权限"
        />
      )}

      {readonly && (
        <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
          <Descriptions.Item label="版本">{readonly.version}</Descriptions.Item>
          <Descriptions.Item label="环境">{readonly.app_env}</Descriptions.Item>
          <Descriptions.Item label="数据库">{readonly.database_url}</Descriptions.Item>
          <Descriptions.Item label="SECRET_KEY">
            {readonly.secret_key_set ? "已自定义" : "使用默认值（生产环境请修改）"}
          </Descriptions.Item>
        </Descriptions>
      )}

      <Alert
        type={platform?.dry_run ? "warning" : "success"}
        showIcon
        style={{ marginBottom: 16 }}
        message={platform?.dry_run ? "Dry-run 模式（模拟下发）" : "生产模式（真实下发）"}
        description={
          platform?.dry_run
            ? "开启后配置仅渲染预览、不推送到真实设备。"
            : "配置将通过 NETCONF/SSH 真实下发到设备，请确认设备凭证与网络可达性。"
        }
      />

      <Form form={form} layout="vertical" className="app-form" disabled={!canEdit || loading}>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item name="dry_run" label="Dry-run（模拟下发）" valuePropName="checked">
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="enable_metrics" label="Prometheus 指标" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="scheduler_enabled" label="后台调度器" valuePropName="checked">
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="auto_learn_on_import"
              label="导入设备后自动现网学习"
              valuePropName="checked"
              tooltip="CSV 导入或新增设备时自动拉取 running-config 并解析业务/VLAN"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="auto_learn_enabled"
              label="定时现网自学习"
              valuePropName="checked"
              tooltip="后台调度器按间隔自动拉取所有在线设备的 running-config，发现线下新增 S-VID 占用"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="protect_live_config"
              label="现网配置保护"
              valuePropName="checked"
              tooltip="下发前用缓存的现网学习快照刷新接口 S-VID 占用（不增加交换机负担），让冲突预检基于最新现网状态；缺少学习基线的设备会给出告警提示。配置下发统一采用增量合并(merge)，不会整体覆盖现网。"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={12} md={6}>
            <Form.Item name="scheduler_interval_seconds" label="调度间隔 (秒)">
              <InputNumber min={10} max={3600} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item
              name="auto_learn_interval_seconds"
              label="自学习间隔 (秒)"
              tooltip="建议 60 秒，与调度器独立计时"
            >
              <InputNumber min={30} max={3600} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="controller_bgp_asn" label="控制器 BGP ASN">
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="controller_node_id" label="控制器节点 ID">
              <Input />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="access_token_expire_minutes" label="登录 Token 有效期 (分钟)">
              <InputNumber min={5} max={43200} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="notes" label="备注">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </div>
  );
}

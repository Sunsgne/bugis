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
  App as AntApp,
  Typography,
} from "antd";
import SwitchOnOff from "../../components/SwitchOnOff";
import { SaveOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";
import { useAuth } from "../../auth";
import { useTc } from "@/i18n/useTc";

const { Text } = Typography;

export default function GeneralSettings() {
  const { tc } = useTc();
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
      message.success(tc('平台运行参数已保存'));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  return (
    <div className="settings-panel">
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>{tc('平台运行')}</Typography.Title>
          <Text type="secondary">{tc('下发模式、调度器、控制器与认证相关参数')}</Text>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave} disabled={!canEdit}>{tc('保存')}</Button>
      </Space>

      {!canEdit && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={tc("只读：当前账号无修改平台运行参数的权限")}
        />
      )}

      {readonly && (
        <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
          <Descriptions.Item label={tc('版本')}>{readonly.version}</Descriptions.Item>
          <Descriptions.Item label={tc('环境')}>{readonly.app_env}</Descriptions.Item>
          <Descriptions.Item label={tc('数据库')}>{readonly.database_url}</Descriptions.Item>
          <Descriptions.Item label="SECRET_KEY">
            {readonly.secret_key_set ? tc("已自定义") : tc("使用默认值（生产环境请修改）")}
          </Descriptions.Item>
        </Descriptions>
      )}

      <Alert
        type={platform?.dry_run ? "warning" : "success"}
        showIcon
        style={{ marginBottom: 16 }}
        message={platform?.dry_run ? tc("Dry-run 模式（模拟下发）") : tc("生产模式（真实下发）")}
        description={
          platform?.dry_run
            ? tc("开启后配置仅渲染预览、不推送到真实设备。")
            : tc("配置将通过 NETCONF/SSH 真实下发到设备，请确认设备凭证与网络可达性。")
        }
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message={tc("现网配置自动拉取")}
        description={
          <>{tc('定时拉取 running-config、导入后学习、变更快照等请在')}<Link to="/settings/config-learn">{tc('配置管理')}</Link>{tc('页配置。')}</>
        }
      />

      <Form form={form} layout="vertical" className="app-form" disabled={!canEdit || loading}>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item name="dry_run" label={tc('Dry-run（模拟下发）')} valuePropName="checked">
              <SwitchOnOff />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="enable_metrics" label={tc('Prometheus 指标')} valuePropName="checked">
              <SwitchOnOff />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item name="scheduler_enabled" label={tc('后台调度器')} valuePropName="checked">
              <SwitchOnOff />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="async_provisioning"
              label={tc('异步开通（后台队列）')}
              valuePropName="checked"
              tooltip={tc('开启后开通/拆除请求会进入后台队列(状态=排队中)立即返回，由工作线程异步下发，避免大量并发操作占满请求线程。前端在工单详情/进度弹窗中轮询进度。')}
            >
              <SwitchOnOff />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={12} md={6}>
            <Form.Item
              name="provision_max_concurrency"
              label={tc('并发下发数')}
              tooltip={tc('后台工作线程同时执行的设备下发数量上限。')}
            >
              <InputNumber min={1} max={64} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={12} md={6}>
            <Form.Item name="scheduler_interval_seconds" label={tc('调度间隔 (秒)')}>
              <InputNumber min={10} max={3600} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="controller_bgp_asn" label={tc('控制器 BGP ASN')}>
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={6}>
            <Form.Item name="controller_node_id" label={tc('控制器节点 ID')}>
              <Input />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="access_token_expire_minutes" label={tc('登录 Token 有效期 (分钟)')}>
              <InputNumber min={5} max={43200} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item name="notes" label={tc('备注')}>
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </div>
  );
}

import {
  Alert,
  Button,
  Col,
  Descriptions,
  Form,
  InputNumber,
  Row,
  Space,
  Switch,
  App as AntApp,
  Typography,
} from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";
import { useAuth } from "../../auth";

const { Text } = Typography;

type SchedulerStatus = {
  enabled?: boolean;
  running?: boolean;
  last_learn?: string | null;
  last_learn_devices?: number;
  last_learn_conflicts?: number;
  last_tick?: string | null;
};

export default function ConfigLearnSettings() {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const { platform, loading, saving, save } = usePlatformSettings();
  const { user } = useAuth();
  const canEdit = user?.role === "admin" || user?.role === "operator";
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);

  const loadScheduler = useCallback(async () => {
    try {
      const { data } = await api.get<SchedulerStatus>("/system/scheduler");
      setScheduler(data);
    } catch {
      setScheduler(null);
    }
  }, []);

  useEffect(() => {
    if (platform) {
      form.setFieldsValue({
        auto_learn_on_import: platform.auto_learn_on_import,
        auto_learn_enabled: platform.auto_learn_enabled,
        auto_learn_interval_seconds: platform.auto_learn_interval_seconds,
        protect_live_config: platform.protect_live_config,
        snapshot_before_change: platform.snapshot_before_change,
      });
    }
  }, [platform, form]);

  useEffect(() => {
    loadScheduler();
    const t = setInterval(loadScheduler, 30_000);
    return () => clearInterval(t);
  }, [loadScheduler]);

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save(v);
      message.success("配置管理参数已保存");
      loadScheduler();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  const timedPullOn = Form.useWatch("auto_learn_enabled", form);
  const schedulerOn = platform?.scheduler_enabled !== false;

  return (
    <div className="settings-panel">
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            配置管理 · 现网拉取
          </Typography.Title>
          <Text type="secondary">
            控制配置管理页的自动现网学习（running-config 拉取与解析），与「平台运行 → 后台调度器」配合使用
          </Text>
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
          message="只读：当前账号无修改平台参数的权限"
        />
      )}

      {!schedulerOn && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="后台调度器已关闭"
          description={
            <>
              定时自动拉取依赖后台调度器。请前往
              <Link to="/settings/general"> 平台运行 </Link>
              开启「后台调度器」。
            </>
          }
        />
      )}

      {scheduler && (
        <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
          <Descriptions.Item label="调度器">
            {scheduler.enabled ? (scheduler.running ? "运行中" : "已启用") : "已关闭"}
          </Descriptions.Item>
          <Descriptions.Item label="最近拉取">
            {scheduler.last_learn ? scheduler.last_learn.replace("T", " ").slice(0, 19) : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="最近设备数">
            {scheduler.last_learn_devices ?? "—"}
          </Descriptions.Item>
          <Descriptions.Item label="S-VID 冲突">
            {scheduler.last_learn_conflicts ?? 0}
          </Descriptions.Item>
        </Descriptions>
      )}

      <Form form={form} layout="vertical" className="app-form" disabled={!canEdit || loading}>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item
              name="auto_learn_enabled"
              label="定时自动拉取"
              valuePropName="checked"
              extra="后台按间隔对所有在线设备拉取 running-config，更新现网学习与 S-VID 占用"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="auto_learn_on_import"
              label="导入/新增设备后自动拉取"
              valuePropName="checked"
              extra="CSV 导入或手动新增设备时立即执行一次现网学习"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={12} md={6}>
            <Form.Item
              name="auto_learn_interval_seconds"
              label="拉取间隔 (秒)"
              tooltip="与 SNMP/拨测调度独立计时，建议 60–300 秒"
              rules={[{ required: timedPullOn, message: "请填写拉取间隔" }]}
            >
              <InputNumber
                min={30}
                max={3600}
                style={{ width: "100%" }}
                disabled={!timedPullOn}
              />
            </Form.Item>
          </Col>
        </Row>

        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="变更保护与快照"
          description="以下选项影响开通/拆除前的现网快照与下发前冲突预检，建议保持开启。"
        />

        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item
              name="protect_live_config"
              label="现网配置保护"
              valuePropName="checked"
              tooltip="下发前用缓存的现网学习快照刷新接口 S-VID 占用，让冲突预检基于最新现网状态"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="snapshot_before_change"
              label="变更前自动快照"
              valuePropName="checked"
              tooltip="开通/拆除前自动拉取各目标设备 running-config 存为 pre_change 快照，用于对比与应急还原"
            >
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </div>
  );
}

import {
  Alert,
  Button,
  Col,
  Descriptions,
  Form,
  InputNumber,
  Row,
  Select,
  Space,
  App as AntApp,
  Typography,
} from "antd";
import SwitchOnOff from "../../components/SwitchOnOff";
import { SaveOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";
import { useAuth } from "../../auth";
import { useTc } from "@/i18n/useTc";

const { Text } = Typography;

type SchedulerStatus = {
  enabled?: boolean;
  running?: boolean;
  last_learn?: string | null;
  last_learn_devices?: number;
  last_learn_conflicts?: number;
  last_tick?: string | null;
  auto_learn_enabled?: boolean;
  auto_learn_interval_seconds?: number;
  next_learn_in_seconds?: number | null;
  next_learn_at?: string | null;
  learn_running?: boolean;
};

const INTERVAL_PRESETS = [
  { value: 300, labelKey: "5 分钟 (300)" },
  { value: 600, labelKey: "10 分钟 (600)" },
  { value: 1800, labelKey: "30 分钟 (1800)" },
  { value: 3600, labelKey: "1 小时 (3600)" },
] as const;

function formatDuration(seconds: number, tc: (s: string) => string): string {
  if (seconds < 60) return `${seconds} ${tc("秒")}`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} ${tc("分钟")}`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return m > 0 ? `${h} ${tc("小时")} ${m} ${tc("分钟")}` : `${h} ${tc("小时")}`;
}

export default function ConfigLearnSettings() {
  const { tc } = useTc();
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
      message.success(tc('配置管理参数已保存'));
      loadScheduler();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  const timedPullOn = Form.useWatch("auto_learn_enabled", form);
  const intervalSec = Form.useWatch("auto_learn_interval_seconds", form);
  const schedulerOn = platform?.scheduler_enabled !== false;

  const intervalPreset = INTERVAL_PRESETS.some((p) => p.value === intervalSec)
    ? intervalSec
    : "custom";

  return (
    <div className="settings-panel">
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>{tc('配置管理 · 现网拉取')}</Typography.Title>
          <Text type="secondary">{tc('控制配置管理页的自动现网学习（running-config 拉取与解析），与「平台运行 → 后台调度器」配合使用')}</Text>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave} disabled={!canEdit}>{tc('保存')}</Button>
      </Space>

      {!canEdit && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={tc("只读：当前账号无修改平台参数的权限")}
        />
      )}

      {!schedulerOn && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={tc("后台调度器已关闭")}
          description={
            <>{tc('定时自动拉取依赖后台调度器。请前往')}<Link to="/settings/general">{tc('平台运行')}</Link>{tc('开启「后台调度器」。')}</>
          }
        />
      )}

      {scheduler && (
        <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
          <Descriptions.Item label={tc('调度器')}>
            {scheduler.enabled ? (scheduler.running ? tc("运行中") : tc("已启用")) : tc("已关闭")}
          </Descriptions.Item>
          <Descriptions.Item label={tc('拉取间隔')}>
            {scheduler.auto_learn_interval_seconds != null
              ? formatDuration(scheduler.auto_learn_interval_seconds, tc)
              : "—"}
          </Descriptions.Item>
          <Descriptions.Item label={tc('最近拉取')}>
            {scheduler.last_learn ? scheduler.last_learn.replace("T", " ").slice(0, 19) : "—"}
          </Descriptions.Item>
          <Descriptions.Item label={tc('下次拉取')}>
            {scheduler.learn_running
              ? tc("拉取进行中…")
              : scheduler.next_learn_in_seconds != null
                ? scheduler.next_learn_in_seconds <= 0
                  ? tc("即将开始")
                  : formatDuration(scheduler.next_learn_in_seconds, tc)
                : "—"}
          </Descriptions.Item>
          <Descriptions.Item label={tc('最近设备数')}>
            {scheduler.last_learn_devices ?? "—"}
          </Descriptions.Item>
          <Descriptions.Item label={tc('S-VID 冲突')}>
            {scheduler.last_learn_conflicts ?? 0}
          </Descriptions.Item>
        </Descriptions>
      )}

      <Form form={form} layout="vertical" className="app-form" disabled={!canEdit || loading}>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item
              name="auto_learn_enabled"
              label={tc('定时自动拉取')}
              valuePropName="checked"
              extra={tc("后台按间隔对所有在线设备拉取 running-config，更新现网学习与 S-VID 占用")}
            >
              <SwitchOnOff />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="auto_learn_on_import"
              label={tc('导入/新增设备后自动拉取')}
              valuePropName="checked"
              extra={tc("CSV 导入或手动新增设备时立即执行一次现网学习")}
            >
              <SwitchOnOff />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item label={tc('拉取间隔')}>
              <Select
                value={intervalPreset}
                disabled={!timedPullOn}
                style={{ width: "100%" }}
                options={[
                  ...INTERVAL_PRESETS.map((p) => ({
                    value: p.value,
                    label: tc(p.labelKey),
                  })),
                  { value: "custom", label: tc("自定义") },
                ]}
                onChange={(v) => {
                  if (v !== "custom") {
                    form.setFieldValue("auto_learn_interval_seconds", v);
                  }
                }}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={6}>
            <Form.Item
              name="auto_learn_interval_seconds"
              label={tc('间隔 (秒)')}
              tooltip={tc('与 SNMP/拨测调度独立；大规模现网建议 1800–3600 秒')}
              rules={[{ required: timedPullOn, message: "请填写拉取间隔" }]}
            >
              <InputNumber
                min={30}
                max={3600}
                step={60}
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
          message={tc("与 SNMP 采集独立")}
          description={tc(
            "定时拉取仅更新 running-config 与 S-VID 占用，不影响流量 SNMP 采样。后台调度器 tick 间隔（平台运行页）控制 SNMP/告警频率。",
          )}
        />

        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={tc("变更保护与快照")}
          description={tc('以下选项影响开通/拆除前的现网快照与下发前冲突预检，建议保持开启。')}
        />

        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item
              name="protect_live_config"
              label={tc('现网配置保护')}
              valuePropName="checked"
              tooltip={tc('下发前用缓存的现网学习快照刷新接口 S-VID 占用，让冲突预检基于最新现网状态')}
            >
              <SwitchOnOff />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item
              name="snapshot_before_change"
              label={tc('变更前自动快照')}
              valuePropName="checked"
              tooltip={tc('开通/拆除前自动拉取各目标设备 running-config 存为 pre_change 快照，用于对比与应急还原')}
            >
              <SwitchOnOff />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </div>
  );
}

import { Col, Form, InputNumber, Row, Switch, Typography } from "antd";
import { usePlatformSettings } from "../hooks/usePlatformSettings";
import { useTc } from "@/i18n/useTc";

const { Text } = Typography;

type Props = {
  /** Show platform defaults as field hints. */
  showDefaults?: boolean;
};

export default function CircuitAlarmThresholdFields({ showDefaults = true }: Props) {
  const { tc } = useTc();
  const { platform } = usePlatformSettings();
  const probeEnabled = Form.useWatch("latency_probe_enabled");

  const latencyHint = showDefaults && platform
    ? `平台默认 ${platform.threshold_latency_ms} ms`
    : "留空使用平台默认";
  const lossHint = showDefaults && platform
    ? `平台默认 ${platform.threshold_packet_loss_pct}%`
    : "留空使用平台默认";
  const utilHint = showDefaults && platform
    ? `平台默认 ${platform.threshold_utilization_pct}%`
    : "留空使用平台默认";
  const healthHint = showDefaults && platform
    ? `平台默认 ${platform.threshold_health_score} 分`
    : "留空使用平台默认";

  const qosOn = probeEnabled !== false;

  return (
    <>
      <Form.Item
        name="latency_probe_enabled"
        label={tc('延迟探测')}
        valuePropName="checked"
        extra="关闭后不对该专线进行路径拨测，监控页不展示时延/抖动/丢包"
      >
        <Switch checkedChildren="开启" unCheckedChildren="关闭" />
      </Form.Item>
      <Text type="secondary" style={{ display: "block", marginBottom: 12, fontSize: 12 }}>
        告警评估使用以下阈值；留空则继承「设置 → 告警阈值」中的平台默认值。
        {!qosOn && (
          <Text type="warning" style={{ marginLeft: 8 }}>{tc('延迟探测已关闭，时延与丢包阈值不生效')}</Text>
        )}
      </Text>
      <Row gutter={16}>
        {qosOn && (
          <>
            <Col span={12}>
              <Form.Item name="alarm_latency_ms" label={tc('时延告警 (ms)')} extra={latencyHint}>
                <InputNumber min={0} max={10000} style={{ width: "100%" }} placeholder={tc('平台默认')} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="alarm_packet_loss_pct" label={tc('丢包告警 (%)')} extra={lossHint}>
                <InputNumber min={0} max={100} step={0.1} style={{ width: "100%" }} placeholder={tc('平台默认')} />
              </Form.Item>
            </Col>
          </>
        )}
        <Col span={12}>
          <Form.Item name="alarm_utilization_pct" label={tc('峰值利用率告警 (%)')} extra={utilHint}>
            <InputNumber min={0} max={100} style={{ width: "100%" }} placeholder={tc('平台默认')} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="alarm_health_score_min" label={tc('健康分下限')} extra={healthHint}>
            <InputNumber min={0} max={100} style={{ width: "100%" }} placeholder={tc('平台默认')} />
          </Form.Item>
        </Col>
      </Row>
    </>
  );
}

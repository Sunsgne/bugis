import { Checkbox, Col, Form, InputNumber, Row, Typography } from "antd";
import { usePlatformSettings } from "../hooks/usePlatformSettings";
import { useTc } from "@/i18n/useTc";
import SwitchOnOff from "./SwitchOnOff";
import { ALARM_KIND } from "../constants/statusLabels";
import {
  CIRCUIT_ALARM_KINDS,
  DEFAULT_ALARM_SUPPRESS_MINUTES,
  DEFAULT_CIRCUIT_ALARM_KINDS,
} from "../constants/circuitAlarms";

const { Text } = Typography;

type Props = {
  /** Show platform defaults as field hints. */
  showDefaults?: boolean;
  /** Show alarm kind multi-select and post-provision suppress duration. */
  showAlarmPolicy?: boolean;
};

export default function CircuitAlarmThresholdFields({
  showDefaults = true,
  showAlarmPolicy = true,
}: Props) {
  const { tc } = useTc();
  const { platform } = usePlatformSettings();
  const probeEnabled = Form.useWatch("latency_probe_enabled");

  const latencyHint = showDefaults && platform
    ? `${tc("平台默认")} ${platform.threshold_latency_ms} ms`
    : tc("留空使用平台默认");
  const lossHint = showDefaults && platform
    ? `${tc("平台默认")} ${platform.threshold_packet_loss_pct}%`
    : tc("留空使用平台默认");
  const utilHint = showDefaults && platform
    ? `${tc("平台默认")} ${platform.threshold_utilization_pct}%`
    : tc("留空使用平台默认");
  const healthHint = showDefaults && platform
    ? `${tc("平台默认")} ${platform.threshold_health_score} ${tc("分")}`
    : tc("留空使用平台默认");

  const qosOn = probeEnabled !== false;

  return (
    <>
      {showAlarmPolicy && (
        <>
          <Form.Item
            name="alarm_suppress_minutes"
            label={tc("开通后告警抑制")}
            initialValue={DEFAULT_ALARM_SUPPRESS_MINUTES}
            extra={tc("专线首次开通成功后，在此时间内不触发新告警（默认 60 分钟）")}
          >
            <InputNumber min={0} max={24 * 60} addonAfter={tc("分钟")} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            name="enabled_alarm_kinds"
            label={tc("告警类型")}
            initialValue={DEFAULT_CIRCUIT_ALARM_KINDS}
            extra={tc("选择该专线需要评估的告警类型；未勾选的类型不会触发告警")}
          >
            <Checkbox.Group style={{ width: "100%" }}>
              <Row gutter={[8, 8]}>
                {CIRCUIT_ALARM_KINDS.map((kind) => (
                  <Col span={12} key={kind}>
                    <Checkbox value={kind}>{ALARM_KIND[kind]}</Checkbox>
                  </Col>
                ))}
              </Row>
            </Checkbox.Group>
          </Form.Item>
        </>
      )}
      <Form.Item
        name="latency_probe_enabled"
        label={tc("延迟探测")}
        valuePropName="checked"
        extra={tc("关闭后不对该专线进行路径拨测，监控页不展示时延/抖动/丢包")}
      >
        <SwitchOnOff />
      </Form.Item>
      <Text type="secondary" style={{ display: "block", marginBottom: 12, fontSize: 12 }}>
        {tc("告警评估使用以下阈值；留空则继承「设置 → 告警阈值」中的平台默认值。")}
        {!qosOn && (
          <Text type="warning" style={{ marginLeft: 8 }}>{tc("延迟探测已关闭，时延与丢包阈值不生效")}</Text>
        )}
      </Text>
      <Row gutter={16}>
        {qosOn && (
          <>
            <Col span={12}>
              <Form.Item name="alarm_latency_ms" label={tc("时延告警 (ms)")} extra={latencyHint}>
                <InputNumber min={0} max={10000} style={{ width: "100%" }} placeholder={tc("平台默认")} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="alarm_packet_loss_pct" label={tc("丢包告警 (%)")} extra={lossHint}>
                <InputNumber min={0} max={100} step={0.1} style={{ width: "100%" }} placeholder={tc("平台默认")} />
              </Form.Item>
            </Col>
          </>
        )}
        <Col span={12}>
          <Form.Item name="alarm_utilization_pct" label={tc("峰值利用率告警 (%)")} extra={utilHint}>
            <InputNumber min={0} max={100} style={{ width: "100%" }} placeholder={tc("平台默认")} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="alarm_health_score_min" label={tc("健康分下限")} extra={healthHint}>
            <InputNumber min={0} max={100} style={{ width: "100%" }} placeholder={tc("平台默认")} />
          </Form.Item>
        </Col>
      </Row>
    </>
  );
}

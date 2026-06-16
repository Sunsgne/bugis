import { Button, Col, Form, InputNumber, Row, Space, App as AntApp, Typography } from "antd";
import { SaveOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { usePlatformSettings } from "../../hooks/usePlatformSettings";

export default function AlarmSettings() {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const { platform, loading, saving, save } = usePlatformSettings();

  useEffect(() => {
    if (platform) {
      form.setFieldsValue({
        threshold_packet_loss_pct: platform.threshold_packet_loss_pct,
        threshold_latency_ms: platform.threshold_latency_ms,
        threshold_utilization_pct: platform.threshold_utilization_pct,
        threshold_health_score: platform.threshold_health_score,
        threshold_link_utilization_pct: platform.threshold_link_utilization_pct,
      });
    }
  }, [platform, form]);

  async function onSave() {
    const v = await form.validateFields();
    try {
      await save(v);
      message.success("告警阈值已保存");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    }
  }

  return (
    <div className="settings-panel">
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            告警阈值
          </Typography.Title>
          <Typography.Text type="secondary">调度器评估 SLA / 容量告警时使用</Typography.Text>
        </div>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={onSave}>
          保存
        </Button>
      </Space>
      <Form form={form} layout="vertical" className="app-form" disabled={loading}>
        <Row gutter={16}>
          <Col xs={12} md={8}>
            <Form.Item name="threshold_packet_loss_pct" label="丢包率阈值 (%)">
              <InputNumber min={0} max={100} step={0.1} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={8}>
            <Form.Item name="threshold_latency_ms" label="时延阈值 (ms)">
              <InputNumber min={0} max={10000} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={8}>
            <Form.Item name="threshold_utilization_pct" label="峰值利用率阈值 (%)">
              <InputNumber min={0} max={100} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={8}>
            <Form.Item name="threshold_health_score" label="健康分下限">
              <InputNumber min={0} max={100} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} md={8}>
            <Form.Item name="threshold_link_utilization_pct" label="链路利用率阈值 (%)">
              <InputNumber min={0} max={100} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </div>
  );
}

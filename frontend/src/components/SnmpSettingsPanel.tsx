import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Switch,
  Tabs,
  Tag,
  App as AntApp,
  Typography,
} from "antd";
import { SaveOutlined, ExperimentOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Device } from "../api/types";

const { Text, Paragraph } = Typography;

interface SnmpSettings {
  id: number;
  enabled: boolean;
  version: string;
  community: string;
  write_community?: string;
  port: number;
  timeout_sec: number;
  retries: number;
  max_repetitions: number;
  prefer_device_community: boolean;
  walk_if_descr: boolean;
  walk_if_alias: boolean;
  walk_if_high_speed: boolean;
  walk_if_oper_status: boolean;
  sync_link_capacity: boolean;
  auto_discover_on_check: boolean;
  exclude_name_patterns?: string[];
  include_name_patterns?: string[];
  v3_username?: string;
  v3_security_level: string;
  v3_auth_protocol?: string;
  v3_priv_protocol?: string;
  v3_context_name?: string;
  v3_auth_password_set?: boolean;
  v3_priv_password_set?: boolean;
  baseline_community: string;
  notes?: string;
}

interface SnmpTestResult {
  ok: boolean;
  target: string;
  version: string;
  interfaces_found: number;
  sample_interfaces: string[];
  latency_ms?: number;
  detail?: string;
}

const AUTH_PROTOS = ["MD5", "SHA", "SHA224", "SHA256", "SHA384", "SHA512"];
const PRIV_PROTOS = ["DES", "AES", "AES128", "AES192", "AES256"];
const SEC_LEVELS = [
  { value: "noAuthNoPriv", label: "noAuthNoPriv" },
  { value: "authNoPriv", label: "authNoPriv" },
  { value: "authPriv", label: "authPriv" },
];

export default function SnmpSettingsPanel() {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testOpen, setTestOpen] = useState(false);
  const [testForm] = Form.useForm();
  const [testResult, setTestResult] = useState<SnmpTestResult | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const watchVersion = Form.useWatch("version", form);

  async function load() {
    setLoading(true);
    try {
      const { data } = await api.get<SnmpSettings>("/system/snmp");
      form.setFieldsValue(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    api.get<Device[]>("/devices").then(({ data }) => setDevices(data)).catch(() => setDevices([]));
  }, []);

  async function save() {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const payload = { ...values };
      if (!payload.v3_auth_password) delete payload.v3_auth_password;
      if (!payload.v3_priv_password) delete payload.v3_priv_password;
      await api.patch("/system/snmp", payload);
      message.success("SNMP 参数已保存");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function runTest() {
    const v = await testForm.validateFields();
    setTestResult(null);
    try {
      const { data } = await api.post<SnmpTestResult>("/system/snmp/test", v);
      setTestResult(data);
      if (data.ok) message.success(`探测成功 · ${data.interfaces_found} 个接口`);
      else message.error(data.detail || "探测失败");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "探测失败");
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: "100%", justifyContent: "space-between" }}>
        <div>
          <Typography.Title level={5} style={{ margin: 0 }}>
            SNMP 采集
          </Typography.Title>
          <Text type="secondary">接口发现、检测与 baseline SNMP community</Text>
        </div>
        <Space>
          <Button icon={<ExperimentOutlined />} onClick={() => setTestOpen(true)}>
            连通性测试
          </Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
            保存
          </Button>
        </Space>
      </Space>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="作用于全平台 SNMP 发现"
        description={
          <Paragraph style={{ marginBottom: 0 }}>
            设备「SNMP 发现」与检测时的 IF-MIB 采集均读取此处。单台设备密码字段可覆盖只读 community。
          </Paragraph>
        }
      />

      <Form form={form} layout="vertical" disabled={loading} initialValues={{ version: "2c", enabled: true }}>
        <Tabs
          items={[
            {
              key: "basic",
              label: "基本",
              children: (
                <>
                  <Row gutter={16}>
                    <Col xs={24} md={8}>
                      <Form.Item name="enabled" label="启用 SNMP 采集" valuePropName="checked">
                        <Switch checkedChildren="开" unCheckedChildren="关" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item name="version" label="SNMP 版本">
                        <Select options={[{ value: "2c", label: "SNMPv2c" }, { value: "3", label: "SNMPv3" }]} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item name="prefer_device_community" label="优先使用设备凭证" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col xs={12} md={6}>
                      <Form.Item name="port" label="UDP 端口">
                        <InputNumber min={1} max={65535} style={{ width: "100%" }} />
                      </Form.Item>
                    </Col>
                    <Col xs={12} md={6}>
                      <Form.Item name="timeout_sec" label="超时 (秒)">
                        <InputNumber min={0.5} max={60} step={0.5} style={{ width: "100%" }} />
                      </Form.Item>
                    </Col>
                    <Col xs={12} md={6}>
                      <Form.Item name="retries" label="重试">
                        <InputNumber min={0} max={10} style={{ width: "100%" }} />
                      </Form.Item>
                    </Col>
                    <Col xs={12} md={6}>
                      <Form.Item name="max_repetitions" label="GETBULK max-rep">
                        <InputNumber min={1} max={100} style={{ width: "100%" }} />
                      </Form.Item>
                    </Col>
                  </Row>
                </>
              ),
            },
            {
              key: "v2c",
              label: "SNMPv2c",
              disabled: watchVersion === "3",
              children: (
                <Row gutter={16}>
                  <Col xs={24} md={12}>
                    <Form.Item name="community" label="只读 Community">
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item name="write_community" label="读写 Community (可选)">
                      <Input />
                    </Form.Item>
                  </Col>
                </Row>
              ),
            },
            {
              key: "v3",
              label: "SNMPv3",
              disabled: watchVersion !== "3",
              children: (
                <>
                  <Row gutter={16}>
                    <Col xs={24} md={8}>
                      <Form.Item name="v3_username" label="用户名">
                        <Input />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item name="v3_security_level" label="安全级别">
                        <Select options={SEC_LEVELS} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item name="v3_context_name" label="Context">
                        <Input />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col xs={24} md={6}>
                      <Form.Item name="v3_auth_protocol" label="认证算法">
                        <Select allowClear options={AUTH_PROTOS.map((v) => ({ value: v, label: v }))} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={6}>
                      <Form.Item name="v3_auth_password" label="认证密码">
                        <Input.Password autoComplete="new-password" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={6}>
                      <Form.Item name="v3_priv_protocol" label="加密算法">
                        <Select allowClear options={PRIV_PROTOS.map((v) => ({ value: v, label: v }))} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={6}>
                      <Form.Item name="v3_priv_password" label="加密密码">
                        <Input.Password autoComplete="new-password" />
                      </Form.Item>
                    </Col>
                  </Row>
                </>
              ),
            },
            {
              key: "mib",
              label: "采集范围",
              children: (
                <>
                  <Row gutter={16}>
                    <Col xs={12} md={6}>
                      <Form.Item name="walk_if_descr" label="ifDescr" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col xs={12} md={6}>
                      <Form.Item name="walk_if_alias" label="ifAlias" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col xs={12} md={6}>
                      <Form.Item name="walk_if_high_speed" label="ifHighSpeed" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col xs={12} md={6}>
                      <Form.Item name="walk_if_oper_status" label="ifOperStatus" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col xs={24} md={12}>
                      <Form.Item name="exclude_name_patterns" label="排除接口 (正则)">
                        <Select mode="tags" tokenSeparators={[","]} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item name="include_name_patterns" label="仅包含 (正则)">
                        <Select mode="tags" tokenSeparators={[","]} />
                      </Form.Item>
                    </Col>
                  </Row>
                </>
              ),
            },
            {
              key: "behavior",
              label: "行为",
              children: (
                <>
                  <Row gutter={16}>
                    <Col xs={24} md={12}>
                      <Form.Item name="sync_link_capacity" label="同步链路容量" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item name="auto_discover_on_check" label="检测时自动发现" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Divider />
                  <Form.Item name="baseline_community" label="初始化模板 Community">
                    <Input style={{ maxWidth: 320 }} />
                  </Form.Item>
                  <Form.Item name="notes" label="备注">
                    <Input.TextArea rows={2} />
                  </Form.Item>
                </>
              ),
            },
          ]}
        />
      </Form>

      <Modal title="SNMP 连通性测试" open={testOpen} onCancel={() => setTestOpen(false)} onOk={runTest} okText="探测" width={560}>
        <Form form={testForm} layout="vertical">
          <Form.Item name="device_id" label="平台设备">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={devices.map((d) => ({ value: d.id, label: `${d.name} (${d.mgmt_ip})` }))}
            />
          </Form.Item>
          <Form.Item name="mgmt_ip" label="或管理 IP">
            <Input />
          </Form.Item>
          <Form.Item name="community" label="临时 Community">
            <Input />
          </Form.Item>
        </Form>
        {testResult && (
          <Alert
            style={{ marginTop: 12 }}
            type={testResult.ok ? "success" : "error"}
            message={testResult.detail || (testResult.ok ? "成功" : "失败")}
            description={
              testResult.sample_interfaces?.length ? (
                <Space wrap>{testResult.sample_interfaces.map((n) => <Tag key={n}>{n}</Tag>)}</Space>
              ) : undefined
            }
          />
        )}
      </Modal>
    </div>
  );
}

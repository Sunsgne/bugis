import {
  Alert,
  Col,
  Collapse,
  Divider,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Switch,
  Typography,
} from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  DEVICE_ROLE_OPTIONS,
  MANAGEMENT_TRANSPORT_OPTIONS,
  OVERLAY_OPTIONS,
  SNMP_V3_SECURITY_OPTIONS,
  SNMP_VERSION_OPTIONS,
  VENDOR_OPTIONS,
} from "@/constants/formOptions";
import type { Device, ManagementDefaults, Site, SnmpDefaults } from "@/api/types";
import { formModalProps } from "@/utils/formModal";

export type DeviceFormValues = {
  name: string;
  vendor: string;
  model?: string;
  role: string;
  overlay_tech: string;
  mgmt_ip: string;
  mgmt_ip_backup?: string;
  mgmt_ip_primary_label?: string;
  mgmt_ip_backup_label?: string;
  loopback_ip?: string;
  bgp_asn?: number | null;
  site_id?: number | null;
  sr_node_sid?: number | null;
  is_route_reflector?: boolean;
  management_transport: string;
  username?: string;
  password?: string;
  enable_password?: string;
  netconf_port: number;
  ssh_port: number;
  netmiko_device_type?: string;
  snmp_enabled: boolean;
  snmp_community?: string;
  snmp_port?: number;
  snmp_version?: string;
  snmp_v3_username?: string;
  snmp_v3_security_level?: string;
  snmp_v3_auth_password?: string;
  snmp_v3_priv_password?: string;
};

const VENDOR_AUTH_HINT: Record<string, string> = {
  h3c: "默认 NETCONF 830 / SSH 22；账号常为 admin 或 netconf",
  huawei: "默认 NETCONF 830；账号常为 netconf 或 huawei",
  juniper: "默认 NETCONF 830；账号常为 netconf",
  arista: "默认 SSH/eAPI；部分场景用 admin",
  cisco: "IOS-XR NETCONF 830；账号常为 admin / cisco",
  frr: "SSH 22，vtysh CLI；账号为 Linux 用户",
};

function defaultValues(mgmt: ManagementDefaults, snmp: SnmpDefaults): Partial<DeviceFormValues> {
  return {
    vendor: "h3c",
    role: "leaf",
    overlay_tech: "vxlan_evpn",
    management_transport: mgmt.management_transport,
    netconf_port: mgmt.netconf_port,
    ssh_port: mgmt.ssh_port,
    username: mgmt.username,
    snmp_enabled: snmp.enabled,
    snmp_port: snmp.port,
    snmp_community: "",
    snmp_version: snmp.version,
    snmp_v3_security_level: "authPriv",
    is_route_reflector: false,
    mgmt_ip_primary_label: mgmt.mgmt_ip_primary_label || "管理网",
    mgmt_ip_backup_label: mgmt.mgmt_ip_backup_label || "公网",
  };
}

export function deviceToFormValues(
  device: Device,
  mgmt: ManagementDefaults,
  snmp: SnmpDefaults,
): DeviceFormValues {
  return {
    name: device.name,
    vendor: device.vendor,
    model: device.model || "",
    role: device.role,
    overlay_tech: device.overlay_tech,
    mgmt_ip: device.mgmt_ip,
    mgmt_ip_backup: device.mgmt_ip_backup || "",
    mgmt_ip_primary_label: device.mgmt_ip_primary_label || "管理网",
    mgmt_ip_backup_label: device.mgmt_ip_backup_label || "公网",
    loopback_ip: device.loopback_ip || "",
    bgp_asn: device.bgp_asn ?? null,
    site_id: device.site_id ?? null,
    sr_node_sid: device.sr_node_sid ?? null,
    is_route_reflector: device.is_route_reflector,
    management_transport: device.management_transport || mgmt.management_transport,
    username: device.username || "",
    password: "",
    enable_password: "",
    netconf_port: device.netconf_port ?? mgmt.netconf_port,
    ssh_port: device.ssh_port ?? mgmt.ssh_port,
    netmiko_device_type: device.netmiko_device_type || "",
    snmp_enabled: device.snmp_enabled !== false,
    snmp_port: device.snmp_port ?? snmp.port,
    snmp_community: "",
    snmp_version: device.snmp_version || snmp.version,
    snmp_v3_username: device.snmp_v3_username || "",
    snmp_v3_security_level: device.snmp_v3_security_level || "authPriv",
    snmp_v3_auth_password: "",
    snmp_v3_priv_password: "",
  };
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode?: "create" | "edit";
  device?: Device | null;
  sites: Site[];
  mgmtDefaults: ManagementDefaults;
  snmpDefaults: SnmpDefaults;
  onSubmit: (values: DeviceFormValues) => Promise<void>;
};

export default function DeviceFormDialog({
  open,
  onOpenChange,
  mode = "create",
  device = null,
  sites,
  mgmtDefaults,
  snmpDefaults,
  onSubmit,
}: Props) {
  const isEdit = mode === "edit";
  const [form] = Form.useForm<DeviceFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const snmpEnabled = Form.useWatch("snmp_enabled", form);
  const snmpVersion = Form.useWatch("snmp_version", form);
  const vendor = Form.useWatch("vendor", form);

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    if (isEdit && device) {
      form.setFieldsValue(deviceToFormValues(device, mgmtDefaults, snmpDefaults));
    } else {
      form.setFieldsValue(defaultValues(mgmtDefaults, snmpDefaults));
    }
  }, [open, isEdit, device, mgmtDefaults, snmpDefaults, form]);

  async function handleOk() {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      await onSubmit(values);
    } catch {
      /* validation errors shown on fields */
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      title={isEdit && device ? `编辑设备 · ${device.name}` : "纳管设备"}
      open={open}
      onOk={handleOk}
      onCancel={() => onOpenChange(false)}
      confirmLoading={submitting}
      okText={isEdit ? "保存" : "创建"}
      cancelText="取消"
      {...formModalProps}
      width={760}
    >
      <Typography.Paragraph type="secondary" style={{ marginTop: 0, marginBottom: 12 }}>
        {isEdit
          ? "修改设备基础信息、南向凭证与 SNMP 配置。密码类字段留空则保持原值。"
          : "填写设备基础信息与南向凭证，SNMP 与登录密码相互独立。"}
      </Typography.Paragraph>

      <Form form={form} layout="vertical" className="app-form" requiredMark="optional">
        {isEdit ? (
          <Alert
            type="warning"
            showIcon
            message="敏感字段不会回显"
            description="登录密码、Enable 密码与 SNMP 密钥留空则不修改。厂商纳管后不可变更。"
            style={{ marginBottom: 16 }}
          />
        ) : (
          <Alert
            type="info"
            showIcon
            message="远程登录凭证说明"
            description={
              <>
                <strong>配置下发 / 初始化</strong> 使用 NETCONF 或 SSH CLI。
                <strong> SNMP 发现</strong> 独立配置 Community / v3。全局默认见{" "}
                <Link to="/settings/management">南向接口</Link> 与 <Link to="/settings/snmp">SNMP 采集</Link>。
              </>
            }
            style={{ marginBottom: 16 }}
          />
        )}

        <Typography.Text strong>基础信息</Typography.Text>
        <Row gutter={16} style={{ marginTop: 12 }}>
          <Col xs={24} sm={12}>
            <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入设备名称" }]}>
              <Input placeholder="BJ-LEAF-01" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="vendor" label="厂商" extra={isEdit ? "纳管后不可修改" : undefined}>
              <Select options={VENDOR_OPTIONS} disabled={isEdit} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="model" label="型号">
              <Input placeholder="S6850 / CE12800 / MX204 …" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="role" label="角色">
              <Select options={DEVICE_ROLE_OPTIONS} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="overlay_tech" label="Overlay">
              <Select options={OVERLAY_OPTIONS} />
            </Form.Item>
          </Col>
          <Col xs={24}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              主/备管理 IP 互为主备：主地址不可达时自动切换至备地址进行 SSH/SNMP/拨测。
            </Typography.Text>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item name="mgmt_ip_primary_label" label="主 IP 类型">
              <Input placeholder="管理网" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={16}>
            <Form.Item name="mgmt_ip" label="主管理 IP" rules={[{ required: true, message: "请输入主管理 IP" }]}>
              <Input placeholder="10.1.0.11 或内网地址" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item name="mgmt_ip_backup_label" label="备 IP 类型">
              <Input placeholder="公网" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={16}>
            <Form.Item name="mgmt_ip_backup" label="备管理 IP">
              <Input placeholder="公网 IP（可选）" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="loopback_ip" label="Loopback">
              <Input placeholder="10.1.255.11" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="bgp_asn" label="BGP ASN">
              <InputNumber min={1} style={{ width: "100%" }} placeholder="65001" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="site_id" label="数据中心">
              <Select
                allowClear
                placeholder="选择站点"
                options={sites.map((s) => ({ value: s.id, label: `${s.code} · ${s.name}` }))}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="sr_node_sid" label="SR Node-SID">
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="is_route_reflector" label="路由反射器" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
        </Row>

        <Divider style={{ margin: "16px 0" }} />

        <Typography.Text strong>南向登录凭证</Typography.Text>
        {vendor && VENDOR_AUTH_HINT[vendor] ? (
          <Typography.Paragraph type="secondary" style={{ marginBottom: 12, marginTop: 4 }}>
            {VENDOR_AUTH_HINT[vendor]}
          </Typography.Paragraph>
        ) : null}
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item name="management_transport" label="配置下发传输">
              <Select options={MANAGEMENT_TRANSPORT_OPTIONS} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="username" label="用户名">
              <Input placeholder="admin / netconf" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="password" label="登录密码">
              <Input.Password
                autoComplete="new-password"
                placeholder={isEdit ? (device?.password_set ? "已配置 · 留空不修改" : "NETCONF / SSH") : "NETCONF / SSH"}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="enable_password" label="Enable 密码">
              <Input.Password
                autoComplete="new-password"
                placeholder={isEdit ? (device?.enable_password_set ? "已配置 · 留空不修改" : "可选") : "可选"}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name="netconf_port"
              label="NETCONF 端口"
              rules={[{ required: true, type: "number", min: 1, max: 65535 }]}
            >
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name="ssh_port"
              label="SSH 端口"
              rules={[{ required: true, type: "number", min: 1, max: 65535 }]}
            >
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col span={24}>
            <Form.Item name="netmiko_device_type" label="Netmiko 设备类型" extra="留空则按厂商自动选择，如 hp_comware、cisco_xr">
              <Input placeholder="留空则按厂商自动选择" />
            </Form.Item>
          </Col>
        </Row>

        <Divider style={{ margin: "16px 0" }} />

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div>
            <Typography.Text strong>SNMP 采集</Typography.Text>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 4 }}>
              默认 Community <Typography.Text code>{snmpDefaults.community}</Typography.Text> · UDP {snmpDefaults.port}
            </Typography.Paragraph>
          </div>
          <Form.Item name="snmp_enabled" valuePropName="checked" style={{ marginBottom: 0 }}>
            <Switch checkedChildren="启用" unCheckedChildren="关闭" />
          </Form.Item>
        </div>

        {snmpEnabled ? (
          <Collapse
            ghost
            defaultActiveKey={["snmp-adv"]}
            items={[
              {
                key: "snmp-adv",
                label: "高级参数（留空则使用平台默认）",
                children: (
                  <Row gutter={16}>
                    <Col xs={24} sm={12}>
                      <Form.Item name="snmp_community" label="Community">
                        <Input
                          placeholder={
                            isEdit && device?.snmp_community_set
                              ? "已配置 · 留空不修改"
                              : snmpDefaults.community
                          }
                        />
                      </Form.Item>
                    </Col>
                    <Col xs={24} sm={12}>
                      <Form.Item
                        name="snmp_port"
                        label="UDP 端口"
                        rules={[{ type: "number", min: 1, max: 65535 }]}
                      >
                        <InputNumber min={1} max={65535} style={{ width: "100%" }} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} sm={12}>
                      <Form.Item name="snmp_version" label="版本">
                        <Select options={SNMP_VERSION_OPTIONS} />
                      </Form.Item>
                    </Col>
                    {snmpVersion === "3" ? (
                      <>
                        <Col xs={24} sm={12}>
                          <Form.Item name="snmp_v3_username" label="SNMPv3 用户名">
                            <Input />
                          </Form.Item>
                        </Col>
                        <Col xs={24} sm={12}>
                          <Form.Item name="snmp_v3_security_level" label="安全级别">
                            <Select options={SNMP_V3_SECURITY_OPTIONS} />
                          </Form.Item>
                        </Col>
                        <Col xs={24} sm={12}>
                          <Form.Item name="snmp_v3_auth_password" label="认证密码">
                            <Input.Password
                              autoComplete="new-password"
                              placeholder={
                                isEdit && device?.snmp_v3_auth_password_set ? "已配置 · 留空不修改" : undefined
                              }
                            />
                          </Form.Item>
                        </Col>
                        <Col xs={24} sm={12}>
                          <Form.Item name="snmp_v3_priv_password" label="加密密码">
                            <Input.Password
                              autoComplete="new-password"
                              placeholder={
                                isEdit && device?.snmp_v3_priv_password_set ? "已配置 · 留空不修改" : undefined
                              }
                            />
                          </Form.Item>
                        </Col>
                      </>
                    ) : null}
                  </Row>
                ),
              },
            ]}
          />
        ) : null}
      </Form>
    </Modal>
  );
}

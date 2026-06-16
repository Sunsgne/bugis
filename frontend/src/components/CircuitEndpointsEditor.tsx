import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Tag,
  Tooltip,
  App as AntApp,
} from "antd";
import type { FormInstance } from "antd";
import { MinusCircleOutlined, PlusOutlined, RadarChartOutlined, WarningOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Device, DeviceInterface, SvidUsage } from "../api/types";
import {
  formatInterfaceShort,
  formatInterfaceTooltip,
  formatOperStatus,
  formatVlanLabel,
} from "../utils/networkDisplay";

const SVID_SOURCE: Record<string, { label: string; color: string }> = {
  platform: { label: "平台", color: "blue" },
  device: { label: "设备", color: "orange" },
  legacy: { label: "手工", color: "red" },
};

function formatPortSpeed(mbps?: number) {
  if (!mbps) return null;
  return mbps >= 1000 ? `${mbps / 1000}G` : `${mbps}M`;
}

function svidUsageLabel(u: SvidUsage) {
  return formatVlanLabel(u.access_mode, u.s_vid, u.c_vid);
}

function svidUsageTitle(u: SvidUsage) {
  const src = SVID_SOURCE[u.source || "platform"]?.label || u.source;
  const parts = [`来源: ${src}`];
  if (u.circuit_code) parts.push(`专线 ${u.circuit_code}`);
  if (u.note) parts.push(u.note);
  return parts.join(" · ");
}

function vlanConflict(
  usage: SvidUsage[] | null | undefined,
  vlanId?: number | null,
  accessMode?: string,
  innerVlanId?: number | null,
  excludeCircuitCode?: string,
): string | null {
  if (!usage?.length) return null;
  if (accessMode === "access") {
    if (usage.some((u) => u.access_mode === "access")) {
      return "该端口已配置 untagged 接入";
    }
    if (usage.length > 0) return "该端口已有 VLAN 封装，无法再配置 untagged";
    return null;
  }
  if (vlanId == null) return null;
  for (const u of usage) {
    if (u.access_mode === "access") return "该端口已配置 untagged，无法叠加 VLAN";
    if (accessMode === "qinq" && u.s_vid === vlanId && u.c_vid === innerVlanId) {
      return `QinQ S:${vlanId}/C:${innerVlanId} 已被占用`;
    }
    if (accessMode !== "qinq" && u.access_mode !== "qinq" && u.s_vid === vlanId) {
      if (excludeCircuitCode && u.circuit_code === excludeCircuitCode) continue;
      return `S-VID ${vlanId} 已被占用`;
    }
  }
  return null;
}

function SvidUsageTags({ list, emptyText }: { list?: SvidUsage[] | null; emptyText?: string }) {
  if (!list?.length) {
    return <span style={{ color: "#52c41a", fontSize: 12 }}>{emptyText || "无占用 · 可分配"}</span>;
  }
  return (
    <Space size={[4, 4]} wrap>
      {list.map((u, idx) => {
        const src = SVID_SOURCE[u.source || "platform"] || SVID_SOURCE.platform;
        return (
          <Tooltip key={idx} title={svidUsageTitle(u)}>
            <Tag color={src.color} style={{ margin: 0 }}>
              {svidUsageLabel(u)}
              <span style={{ opacity: 0.75, marginLeft: 4 }}>({src.label})</span>
            </Tag>
          </Tooltip>
        );
      })}
    </Space>
  );
}

function InterfaceOptionRow({ iface }: { iface: DeviceInterface }) {
  const speed = formatPortSpeed(iface.speed_mbps);
  const used = (iface.used_s_vids?.length || 0) > 0;
  const short = formatInterfaceShort(iface.name);
  return (
    <div className="iface-option">
      <div className="iface-option-head">
        <Tooltip title={short === iface.name ? undefined : formatInterfaceTooltip(iface.name)}>
          <span className="iface-option-name">{short}</span>
        </Tooltip>
        {speed && <Tag bordered={false}>{speed}</Tag>}
        <Tag color={iface.oper_status === "up" ? "success" : "default"} bordered={false}>
          {formatOperStatus(iface.oper_status)}
        </Tag>
        {!used && <Tag color="green" bordered={false}>空闲</Tag>}
      </div>
      {used && (
        <div className="iface-option-svids">
          <SvidUsageTags list={iface.used_s_vids} />
        </div>
      )}
    </div>
  );
}

function PortDetailPanel({
  iface,
  vlanId,
  accessMode,
  innerVlanId,
  excludeCircuitCode,
}: {
  iface?: DeviceInterface;
  vlanId?: number | null;
  accessMode?: string;
  innerVlanId?: number | null;
  excludeCircuitCode?: string;
}) {
  if (!iface) return null;
  const speed = formatPortSpeed(iface.speed_mbps);
  const conflict = vlanConflict(
    iface.used_s_vids,
    vlanId,
    accessMode,
    innerVlanId,
    excludeCircuitCode,
  );
  const short = formatInterfaceShort(iface.name);
  return (
    <div className="port-detail-panel">
      <div className="port-detail-title">
        <Tooltip title={short === iface.name ? undefined : formatInterfaceTooltip(iface.name)}>
          <span>{short}</span>
        </Tooltip>
        {speed && <Tag>{speed}</Tag>}
        <Tag color={iface.oper_status === "up" ? "success" : "default"}>
          {formatOperStatus(iface.oper_status)}
        </Tag>
      </div>
      <div className="port-detail-row">
        <span className="port-detail-label">S-VID 占用</span>
        <SvidUsageTags list={iface.used_s_vids} emptyText="该端口暂无 VLAN 占用" />
      </div>
      {conflict && (
        <Alert type="warning" showIcon icon={<WarningOutlined />} message={conflict} style={{ marginTop: 8 }} />
      )}
    </div>
  );
}

function deviceLabel(d: Device) {
  const sid = d.sr_node_sid ? ` SID:${d.sr_node_sid}` : "";
  return `${d.name} (${d.vendor}/${d.overlay_tech})${sid}`;
}

export interface CircuitEndpointsEditorProps {
  form: FormInstance;
  devices: Device[];
  formLoading?: boolean;
  /** Pre-load interface lists when editing existing endpoints. */
  preloadDeviceIds?: number[];
  minEndpoints?: number;
  /** Ignore S-VID conflicts owned by this circuit (endpoint edit). */
  excludeCircuitCode?: string;
}

export default function CircuitEndpointsEditor({
  form,
  devices,
  formLoading = false,
  preloadDeviceIds = [],
  minEndpoints = 1,
  excludeCircuitCode,
}: CircuitEndpointsEditorProps) {
  const { message } = AntApp.useApp();
  const [ifaceByDevice, setIfaceByDevice] = useState<Record<number, DeviceInterface[]>>({});

  async function loadIfaces(deviceId: number, autoDiscover = true) {
    if (!deviceId) return;
    let { data } = await api.get<DeviceInterface[]>(`/devices/${deviceId}/interfaces`);
    if ((!data || data.length === 0) && autoDiscover) {
      const r = await api.post<DeviceInterface[]>(`/devices/${deviceId}/discover-interfaces`);
      data = r.data;
    }
    setIfaceByDevice((p) => ({ ...p, [deviceId]: data }));
  }

  async function discover(deviceId: number) {
    if (!deviceId) return message.warning("请先选择设备");
    const hide = message.loading("SNMP 发现 + S-VID 扫描...", 0);
    try {
      const { data } = await api.post<DeviceInterface[]>(`/devices/${deviceId}/discover-interfaces`);
      setIfaceByDevice((p) => ({ ...p, [deviceId]: data }));
      message.success(`已发现 ${data.length} 个接口，并更新 VLAN 占用`);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "发现失败");
    } finally {
      hide();
    }
  }

  function ifaceSelectOptions(deviceId: number) {
    return (ifaceByDevice[deviceId] || []).map((iface) => ({
      value: iface.name,
      label: iface.name,
      iface,
    }));
  }

  function findIface(deviceId: number, name?: string) {
    if (!deviceId || !name) return undefined;
    return (ifaceByDevice[deviceId] || []).find((i) => i.name === name);
  }

  useEffect(() => {
    preloadDeviceIds.forEach((id) => {
      if (id) loadIfaces(id, false);
    });
  }, [preloadDeviceIds.join(",")]);

  return (
    <>
      <div className="endpoint-legend">
        图例：
        <Tag color="green" bordered={false}>空闲</Tag>
        <Tag color="blue" bordered={false}>S:VID (平台)</Tag>
        <Tag color="orange" bordered={false}>S:VID (设备)</Tag>
        <Tag color="red" bordered={false}>S:VID (手工)</Tag>
      </div>
      <Form.List name="endpoints">
        {(fields, { add, remove }) => (
          <>
            <div className="endpoint-grid">
              {fields.map((field) => (
                <Form.Item
                  key={field.key}
                  noStyle
                  shouldUpdate={(p, c) => p.endpoints !== c.endpoints}
                >
                  {({ getFieldValue }) => {
                    const ep = getFieldValue(["endpoints", field.name]) || {};
                    const did = ep.device_id as number | undefined;
                    const ifName = ep.interface_name as string | undefined;
                    const selectedIface = findIface(did || 0, ifName);
                    const label = ep.label || String.fromCharCode(65 + field.name);
                    return (
                      <Card
                        size="small"
                        className="endpoint-card"
                        title={
                          <Tag color={label === "A" ? "blue" : label === "Z" ? "purple" : "default"}>
                            端点 {label}
                          </Tag>
                        }
                        extra={
                          fields.length > minEndpoints ? (
                            <Button
                              type="text"
                              danger
                              size="small"
                              icon={<MinusCircleOutlined />}
                              onClick={() => remove(field.name)}
                            />
                          ) : null
                        }
                        style={{ marginBottom: 0 }}
                      >
                        <Row gutter={[16, 0]}>
                          <Col xs={24} sm={8} md={6} lg={5}>
                            <Form.Item
                              name={[field.name, "label"]}
                              label="标签"
                              rules={[{ required: true }]}
                            >
                              <Input placeholder="A" />
                            </Form.Item>
                          </Col>
                          <Col xs={24} sm={16} md={18} lg={19}>
                            <Form.Item
                              name={[field.name, "device_id"]}
                              label="接入设备"
                              rules={[{ required: true, message: "请选择设备" }]}
                            >
                              <Select
                                placeholder="选择 VTEP / PE / Leaf"
                                loading={formLoading}
                                showSearch
                                optionFilterProp="label"
                                onChange={(v) => {
                                  form.setFieldValue(["endpoints", field.name, "interface_name"], undefined);
                                  loadIfaces(v);
                                }}
                                options={devices.map((d) => ({
                                  value: d.id,
                                  label: deviceLabel(d),
                                }))}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Form.Item label="物理端口" required style={{ marginBottom: 12 }}>
                          <div className="endpoint-port-row">
                            <Form.Item
                              name={[field.name, "interface_name"]}
                              rules={[{ required: true, message: "请选择端口" }]}
                              noStyle
                            >
                              <Select
                                placeholder={did ? "选择端口（下拉可查看占用详情）" : "请先选择设备"}
                                showSearch
                                disabled={!did}
                                optionLabelProp="label"
                                popupMatchSelectWidth={520}
                                listHeight={360}
                                notFoundContent={
                                  did ? (
                                    <span style={{ padding: 8, color: "#888" }}>
                                      无接口记录，请点击右侧按钮 SNMP 发现
                                    </span>
                                  ) : (
                                    "请先选择设备"
                                  )
                                }
                                options={ifaceSelectOptions(did || 0)}
                                optionRender={(option) => {
                                  const iface = (option.data as { iface?: DeviceInterface })?.iface;
                                  return iface ? <InterfaceOptionRow iface={iface} /> : option.label;
                                }}
                              />
                            </Form.Item>
                            <Button icon={<RadarChartOutlined />} disabled={!did} onClick={() => discover(did!)}>
                              发现
                            </Button>
                          </div>
                        </Form.Item>

                        {selectedIface && (
                          <PortDetailPanel
                            iface={selectedIface}
                            vlanId={ep.vlan_id}
                            accessMode={ep.access_mode}
                            innerVlanId={ep.inner_vlan_id}
                            excludeCircuitCode={excludeCircuitCode}
                          />
                        )}

                        <Row gutter={[16, 4]} style={{ marginTop: 16 }}>
                          <Col xs={24} sm={12} md={8}>
                            <Form.Item name={[field.name, "access_mode"]} label="封装模式" initialValue="dot1q">
                              <Select
                                options={[
                                  { value: "access", label: "Access · 不带标签" },
                                  { value: "dot1q", label: "Dot1Q · 单标签" },
                                  { value: "qinq", label: "QinQ · 双标签" },
                                ]}
                              />
                            </Form.Item>
                          </Col>
                          <Col xs={24} sm={12} md={ep.access_mode === "qinq" ? 8 : 16}>
                            <Form.Item
                              name={[field.name, "vlan_id"]}
                              label="S-VID"
                              tooltip="Service VLAN，留空则自动分配"
                            >
                              <InputNumber placeholder="自动分配" style={{ width: "100%" }} min={1} max={4094} />
                            </Form.Item>
                          </Col>
                          {ep.access_mode === "qinq" && (
                            <Col xs={24} sm={12} md={8}>
                              <Form.Item name={[field.name, "inner_vlan_id"]} label="C-VID">
                                <InputNumber placeholder="内层 VLAN" style={{ width: "100%" }} min={1} max={4094} />
                              </Form.Item>
                            </Col>
                          )}
                        </Row>
                      </Card>
                    );
                  }}
                </Form.Item>
              ))}
            </div>
            <Button type="dashed" block icon={<PlusOutlined />} onClick={() => add({ label: "", access_mode: "dot1q" })}>
              添加端点
            </Button>
          </>
        )}
      </Form.List>
    </>
  );
}

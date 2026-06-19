import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
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
import { useTc } from "@/i18n/useTc";
import {
  formatInterfaceShort,
  formatInterfaceTooltip,
  formatOperStatus,
  formatVlanLabel,
  isCircuitAccessPort,
} from "../utils/networkDisplay";

const VLAN_MIN = 1;
const VLAN_MAX = 4096;

const SVID_SOURCE: Record<string, { labelKey: string; color: string }> = {
  platform: { labelKey: "平台", color: "blue" },
  device: { labelKey: "设备", color: "orange" },
  legacy: { labelKey: "手工", color: "red" },
};

function formatPortSpeed(mbps?: number) {
  if (!mbps) return null;
  return mbps >= 1000 ? `${mbps / 1000}G` : `${mbps}M`;
}

function svidUsageLabel(u: SvidUsage) {
  return formatVlanLabel(u.access_mode, u.s_vid, u.c_vid);
}

function svidUsageTitle(u: SvidUsage, tc: (s: string) => string) {
  const src = tc(SVID_SOURCE[u.source || "platform"]?.labelKey || u.source || "platform");
  const parts = [`${tc("来源")}: ${src}`];
  if (u.circuit_code) parts.push(`${tc("专线")} ${u.circuit_code}`);
  if (u.note) parts.push(u.note);
  return parts.join(" · ");
}

function skipUsage(
  u: SvidUsage,
  excludeCircuitCode?: string,
  adoptMode?: boolean,
): boolean {
  if (excludeCircuitCode && u.circuit_code === excludeCircuitCode) return true;
  if (adoptMode && u.source === "device") return true;
  return false;
}

function portHasUntagged(usage: SvidUsage[] | null | undefined): boolean {
  return Boolean(usage?.some((u) => u.access_mode === "access"));
}

function isDot1qSvidTaken(
  svid: number,
  usage: SvidUsage[] | null | undefined,
  excludeCircuitCode?: string,
  adoptMode?: boolean,
): boolean {
  if (!usage?.length) return false;
  if (portHasUntagged(usage)) return true;
  for (const u of usage) {
    if (skipUsage(u, excludeCircuitCode, adoptMode)) continue;
    if (u.access_mode !== "qinq" && u.s_vid === svid) return true;
  }
  return false;
}

function isQinqSvidTaken(
  svid: number,
  usage: SvidUsage[] | null | undefined,
  excludeCircuitCode?: string,
  adoptMode?: boolean,
): boolean {
  if (!usage?.length) return false;
  if (portHasUntagged(usage)) return true;
  for (const u of usage) {
    if (skipUsage(u, excludeCircuitCode, adoptMode)) continue;
    if (u.access_mode !== "qinq" && u.s_vid === svid) return true;
  }
  return false;
}

function isQinqPairTaken(
  svid: number,
  cvid: number,
  usage: SvidUsage[] | null | undefined,
  excludeCircuitCode?: string,
  adoptMode?: boolean,
): boolean {
  if (!usage?.length) return false;
  if (portHasUntagged(usage)) return true;
  for (const u of usage) {
    if (skipUsage(u, excludeCircuitCode, adoptMode)) continue;
    if (u.access_mode === "qinq" && u.s_vid === svid && u.c_vid === cvid) return true;
    if (u.access_mode !== "qinq" && u.s_vid === svid) return true;
  }
  return false;
}

function vlanConflict(
  usage: SvidUsage[] | null | undefined,
  vlanId?: number | null,
  accessMode?: string,
  innerVlanId?: number | null,
  excludeCircuitCode?: string,
  adoptMode?: boolean,
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
    if (adoptMode && u.source === "device") {
      if (accessMode === "qinq" && u.s_vid === vlanId && u.c_vid === innerVlanId) continue;
      if (accessMode !== "qinq" && u.access_mode !== "qinq" && u.s_vid === vlanId) continue;
    }
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

function buildVlanOptions(
  accessMode: string,
  usage: SvidUsage[] | null | undefined,
  tc: (s: string) => string,
  kind: "svid" | "cvid",
  selectedSvid?: number | null,
  excludeCircuitCode?: string,
  adoptMode?: boolean,
) {
  const occupiedLabel = tc("已占用");
  const options: { value: number; label: string; disabled: boolean }[] = [];
  for (let v = VLAN_MIN; v <= VLAN_MAX; v += 1) {
    let disabled = false;
    if (kind === "svid") {
      if (accessMode === "dot1q") {
        disabled = isDot1qSvidTaken(v, usage, excludeCircuitCode, adoptMode);
      } else if (accessMode === "qinq") {
        disabled = isQinqSvidTaken(v, usage, excludeCircuitCode, adoptMode);
      }
    } else if (kind === "cvid" && selectedSvid != null) {
      disabled = isQinqPairTaken(selectedSvid, v, usage, excludeCircuitCode, adoptMode);
    }
    options.push({
      value: v,
      label: disabled ? `${v} · ${occupiedLabel}` : String(v),
      disabled,
    });
  }
  return options;
}

function SvidUsageTags({
  list,
  emptyText,
  tc,
}: {
  list?: SvidUsage[] | null;
  emptyText?: string;
  tc: (s: string) => string;
}) {
  if (!list?.length) {
    return (
      <span style={{ color: "#52c41a", fontSize: 12 }}>
        {emptyText || tc("无占用 · 可分配")}
      </span>
    );
  }
  return (
    <Space size={[4, 4]} wrap>
      {list.map((u, idx) => {
        const src = SVID_SOURCE[u.source || "platform"] || SVID_SOURCE.platform;
        return (
          <Tooltip key={idx} title={svidUsageTitle(u, tc)}>
            <Tag color={src.color} style={{ margin: 0 }}>
              {svidUsageLabel(u)}
              <span style={{ opacity: 0.75, marginLeft: 4 }}>({tc(src.labelKey)})</span>
            </Tag>
          </Tooltip>
        );
      })}
    </Space>
  );
}

function interfaceOptionLabel(iface: DeviceInterface) {
  const short = formatInterfaceShort(iface.name);
  const desc = iface.description?.trim();
  if (!desc) return short;
  const clipped = desc.length > 56 ? `${desc.slice(0, 53)}…` : desc;
  return `${short} — ${clipped}`;
}

function InterfaceOptionRow({ iface }: { iface: DeviceInterface }) {
  const { tc } = useTc();
  const speed = formatPortSpeed(iface.speed_mbps);
  const used = (iface.used_s_vids?.length || 0) > 0;
  const short = formatInterfaceShort(iface.name);
  const desc = iface.description?.trim();
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
        {!used && <Tag color="green" bordered={false}>{tc("空闲")}</Tag>}
      </div>
      {desc && (
        <div className="iface-option-desc" title={desc}>
          {desc}
        </div>
      )}
      {used && (
        <div className="iface-option-svids">
          <SvidUsageTags list={iface.used_s_vids} tc={tc} />
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
  adoptMode,
}: {
  iface?: DeviceInterface;
  vlanId?: number | null;
  accessMode?: string;
  innerVlanId?: number | null;
  excludeCircuitCode?: string;
  adoptMode?: boolean;
}) {
  const { tc } = useTc();
  if (!iface) return null;
  const speed = formatPortSpeed(iface.speed_mbps);
  const conflict = vlanConflict(
    iface.used_s_vids,
    vlanId,
    accessMode,
    innerVlanId,
    excludeCircuitCode,
    adoptMode,
  );
  const short = formatInterfaceShort(iface.name);
  const desc = iface.description?.trim();
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
      {desc && (
        <div className="port-detail-row">
          <span className="port-detail-label">{tc("端口描述")}</span>
          <span className="port-detail-value">{desc}</span>
        </div>
      )}
      <div className="port-detail-row">
        <span className="port-detail-label">{tc("S-VID 占用")}</span>
        <SvidUsageTags list={iface.used_s_vids} emptyText={tc("该端口暂无 VLAN 占用")} tc={tc} />
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

type EndpointCardProps = {
  field: { name: number; key: number };
  ep: Record<string, unknown>;
  form: FormInstance;
  devices: Device[];
  formLoading: boolean;
  minEndpoints: number;
  fieldsLength: number;
  onRemove: () => void;
  ifaceByDevice: Record<number, DeviceInterface[]>;
  loadIfaces: (deviceId: number) => void;
  discover: (deviceId: number) => void;
  excludeCircuitCode?: string;
  adoptMode: boolean;
};

function EndpointCard({
  field,
  ep,
  form,
  devices,
  formLoading,
  minEndpoints,
  fieldsLength,
  onRemove,
  ifaceByDevice,
  loadIfaces,
  discover,
  excludeCircuitCode,
  adoptMode,
}: EndpointCardProps) {
  const { tc } = useTc();
  const did = ep.device_id as number | undefined;
  const ifName = ep.interface_name as string | undefined;
  const accessMode = (ep.access_mode as string) || "dot1q";
  const vlanId = ep.vlan_id as number | undefined;
  const selectedIface = did && ifName
    ? (ifaceByDevice[did] || []).find((i) => i.name === ifName)
    : undefined;
  const label = (ep.label as string) || String.fromCharCode(65 + field.name);
  const vlanDisabled = !selectedIface || accessMode === "access";
  const usage = selectedIface?.used_s_vids;

  const svidOptions = useMemo(
    () =>
      selectedIface && accessMode !== "access"
        ? buildVlanOptions(accessMode, usage, tc, "svid", vlanId, excludeCircuitCode, adoptMode)
        : [],
    [selectedIface, accessMode, usage, tc, vlanId, excludeCircuitCode, adoptMode],
  );

  const cvidOptions = useMemo(
    () =>
      selectedIface && accessMode === "qinq"
        ? buildVlanOptions(accessMode, usage, tc, "cvid", vlanId, excludeCircuitCode, adoptMode)
        : [],
    [selectedIface, accessMode, usage, tc, vlanId, excludeCircuitCode, adoptMode],
  );

  const allIfaces = ifaceByDevice[did || 0] || [];
  const portOptions = allIfaces
    .filter((iface) => isCircuitAccessPort(iface.name))
    .map((iface) => ({
      value: iface.name,
      label: interfaceOptionLabel(iface),
      iface,
    }));

  return (
    <Card
      size="small"
      className="endpoint-card"
      title={
        <Tag color={label === "A" ? "blue" : label === "Z" ? "purple" : "default"}>
          {tc("端点")} {label}
        </Tag>
      }
      extra={
        fieldsLength > minEndpoints ? (
          <Button type="text" danger size="small" icon={<MinusCircleOutlined />} onClick={onRemove} />
        ) : null
      }
      style={{ marginBottom: 0 }}
    >
      <Row gutter={[16, 0]}>
        <Col xs={24} sm={8} md={6} lg={5}>
          <Form.Item name={[field.name, "label"]} label={tc("标签")} rules={[{ required: true }]}>
            <Input placeholder="A" />
          </Form.Item>
        </Col>
        <Col xs={24} sm={16} md={18} lg={19}>
          <Form.Item
            name={[field.name, "device_id"]}
            label={tc("接入设备")}
            rules={[{ required: true, message: tc("请选择设备") }]}
          >
            <Select
              placeholder={tc("选择 VTEP / PE / Leaf")}
              loading={formLoading}
              showSearch
              optionFilterProp="label"
              onChange={(v) => {
                form.setFieldValue(["endpoints", field.name, "interface_name"], undefined);
                form.setFieldValue(["endpoints", field.name, "vlan_id"], undefined);
                form.setFieldValue(["endpoints", field.name, "inner_vlan_id"], undefined);
                loadIfaces(v);
              }}
              options={devices.map((d) => ({ value: d.id, label: deviceLabel(d) }))}
            />
          </Form.Item>
        </Col>
      </Row>

      <Form.Item label={tc("物理端口")} required style={{ marginBottom: 12 }}>
        <div className="endpoint-port-row">
          <Form.Item
            name={[field.name, "interface_name"]}
            rules={[{ required: true, message: tc("请选择端口") }]}
            noStyle
          >
            <Select
              placeholder={did ? tc("选择端口（下拉可查看占用详情）") : tc("请先选择设备")}
              showSearch
              disabled={!did}
              optionLabelProp="label"
              popupMatchSelectWidth={520}
              listHeight={360}
              notFoundContent={
                did ? (
                  allIfaces.length > 0 && portOptions.length === 0 ? (
                    <span style={{ padding: 8, color: "#888" }}>{tc("无物理/聚合口记录，请 SNMP 发现")}</span>
                  ) : (
                    <span style={{ padding: 8, color: "#888" }}>{tc("无接口记录，请点击右侧按钮 SNMP 发现")}</span>
                  )
                ) : (
                  tc("请先选择设备")
                )
              }
              options={portOptions}
              onChange={() => {
                form.setFieldValue(["endpoints", field.name, "vlan_id"], undefined);
                form.setFieldValue(["endpoints", field.name, "inner_vlan_id"], undefined);
              }}
              optionRender={(option) => {
                const iface = (option.data as { iface?: DeviceInterface })?.iface;
                return iface ? <InterfaceOptionRow iface={iface} /> : option.label;
              }}
            />
          </Form.Item>
          <Button icon={<RadarChartOutlined />} disabled={!did} onClick={() => did && discover(did)}>
            {tc("发现")}
          </Button>
        </div>
      </Form.Item>

      <Row gutter={[16, 4]} style={{ marginBottom: selectedIface ? 12 : 0 }}>
        <Col xs={24} sm={12} md={8}>
          <Form.Item name={[field.name, "access_mode"]} label={tc("封装模式")} initialValue="dot1q">
            <Select
              disabled={!selectedIface}
              options={[
                { value: "access", label: tc("Access · 不带标签") },
                { value: "dot1q", label: tc("Dot1Q · 单标签") },
                { value: "qinq", label: tc("QinQ · 双标签") },
              ]}
              onChange={(mode) => {
                if (mode === "access") {
                  form.setFieldValue(["endpoints", field.name, "vlan_id"], undefined);
                  form.setFieldValue(["endpoints", field.name, "inner_vlan_id"], undefined);
                } else if (mode === "dot1q") {
                  form.setFieldValue(["endpoints", field.name, "inner_vlan_id"], undefined);
                }
              }}
            />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12} md={accessMode === "qinq" ? 8 : 16}>
          <Form.Item
            name={[field.name, "vlan_id"]}
            label="S-VID"
            tooltip={
              accessMode === "access"
                ? tc("Access 模式无需 VLAN 标签")
                : tc("Service VLAN，留空则自动分配")
            }
          >
            <Select
              allowClear
              showSearch
              disabled={vlanDisabled}
              placeholder={accessMode === "access" ? tc("无需配置") : tc("自动分配")}
              optionFilterProp="label"
              options={svidOptions}
              listHeight={320}
              virtual
              onChange={() => {
                if (accessMode === "qinq") {
                  form.setFieldValue(["endpoints", field.name, "inner_vlan_id"], undefined);
                }
              }}
            />
          </Form.Item>
        </Col>
        {accessMode === "qinq" && (
          <Col xs={24} sm={12} md={8}>
            <Form.Item name={[field.name, "inner_vlan_id"]} label="C-VID">
              <Select
                allowClear
                showSearch
                disabled={vlanDisabled || vlanId == null}
                placeholder={vlanId == null ? tc("请先选择 S-VID") : tc("内层 VLAN")}
                optionFilterProp="label"
                options={cvidOptions}
                listHeight={320}
                virtual
              />
            </Form.Item>
          </Col>
        )}
      </Row>

      {selectedIface && (
        <PortDetailPanel
          iface={selectedIface}
          vlanId={vlanId}
          accessMode={accessMode}
          innerVlanId={ep.inner_vlan_id as number | undefined}
          excludeCircuitCode={excludeCircuitCode}
          adoptMode={adoptMode}
        />
      )}
    </Card>
  );
}

export interface CircuitEndpointsEditorProps {
  form: FormInstance;
  devices: Device[];
  formLoading?: boolean;
  preloadDeviceIds?: number[];
  minEndpoints?: number;
  excludeCircuitCode?: string;
  adoptMode?: boolean;
}

export default function CircuitEndpointsEditor({
  form,
  devices,
  formLoading = false,
  preloadDeviceIds = [],
  minEndpoints = 1,
  excludeCircuitCode,
  adoptMode = false,
}: CircuitEndpointsEditorProps) {
  const { tc } = useTc();
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
    if (!deviceId) return message.warning(tc("请先选择设备"));
    const hide = message.loading(tc("SNMP 发现 + S-VID 扫描..."), 0);
    try {
      const { data } = await api.post<DeviceInterface[]>(`/devices/${deviceId}/discover-interfaces`);
      setIfaceByDevice((p) => ({ ...p, [deviceId]: data }));
      message.success(`${tc("已发现")} ${data.length} ${tc("个接口，并更新 VLAN 占用")}`);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("发现失败"));
    } finally {
      hide();
    }
  }

  useEffect(() => {
    preloadDeviceIds.forEach((id) => {
      if (id) loadIfaces(id, false);
    });
  }, [preloadDeviceIds.join(",")]);

  return (
    <>
      <div className="endpoint-legend">
        {tc("图例：")}
        <Tag color="green" bordered={false}>{tc("空闲")}</Tag>
        <Tag color="blue" bordered={false}>{tc("S:VID (平台)")}</Tag>
        <Tag color="orange" bordered={false}>{tc("S:VID (设备)")}</Tag>
        <Tag color="red" bordered={false}>{tc("S:VID (手工)")}</Tag>
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
                    return (
                      <EndpointCard
                        field={field}
                        ep={ep}
                        form={form}
                        devices={devices}
                        formLoading={formLoading}
                        minEndpoints={minEndpoints}
                        fieldsLength={fields.length}
                        onRemove={() => remove(field.name)}
                        ifaceByDevice={ifaceByDevice}
                        loadIfaces={(id) => loadIfaces(id, false)}
                        discover={discover}
                        excludeCircuitCode={excludeCircuitCode}
                        adoptMode={adoptMode}
                      />
                    );
                  }}
                </Form.Item>
              ))}
            </div>
            <Button type="dashed" block icon={<PlusOutlined />} onClick={() => add({ label: "", access_mode: "dot1q" })}>
              {tc("添加端点")}
            </Button>
          </>
        )}
      </Form.List>
    </>
  );
}

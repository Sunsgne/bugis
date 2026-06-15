import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  App as AntApp,
  Popconfirm,
  Descriptions,
  Drawer,
  Collapse,
  Timeline,
  Row,
  Col,
  Statistic,
  Switch,
  Segmented,
  Alert,
  Divider,
  Typography,
} from "antd";
import {
  PlusOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  MinusCircleOutlined,
  EditOutlined,
  DownloadOutlined,
  HistoryOutlined,
  RadarChartOutlined,
  DeleteOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import type { Circuit, Device, DeviceInterface, Offering, Site, SvidUsage, Tenant } from "../api/types";
import { configPreviewModalProps, ConfigPreviewPre, createCircuitModalProps } from "../utils/configPreview";
import { TenantSearchSelect, useTenantSearch } from "../components/TenantSearchSelect";
import OfferingSearchSelect, { useOfferingSearch } from "../components/OfferingSearchSelect";

const SERVICE_LABEL: Record<string, string> = {
  l2vpn_evpn: "EVPN L2VPN",
  l3vpn_evpn: "EVPN L3VPN",
  evpn_vpws: "EVPN-VPWS",
  dci: "DCI 互联",
  remote_ipt: "Remote IPT",
};
const EGRESS_COUNTRIES = [
  { value: "CN", label: "中国 CN" },
  { value: "HK", label: "香港 HK" },
  { value: "SG", label: "新加坡 SG" },
  { value: "JP", label: "日本 JP" },
  { value: "US", label: "美国 US" },
  { value: "GB", label: "英国 GB" },
  { value: "DE", label: "德国 DE" },
  { value: "AU", label: "澳大利亚 AU" },
  { value: "TW", label: "台湾 TW" },
  { value: "KR", label: "韩国 KR" },
];
const STATUS_COLOR: Record<string, string> = {
  draft: "default",
  pending: "gold",
  provisioning: "processing",
  active: "green",
  degraded: "orange",
  suspended: "volcano",
  decommissioned: "default",
  failed: "red",
};

interface TenantSummary {
  tenant_id: number;
  circuits_total: number;
  circuits_active: number;
  circuits_decommissioned: number;
  circuits_draft: number;
  total_bandwidth_mbps: number;
  active_bandwidth_mbps: number;
  by_service_type: Record<string, number>;
}

interface TenantOverview {
  tenants_total: number;
  circuits_total: number;
  circuits_active: number;
  circuits_decommissioned: number;
  circuits_draft: number;
  active_bandwidth_mbps: number;
}

const DELETABLE = new Set(["decommissioned", "draft", "failed"]);

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
  if (u.access_mode === "access") return "untagged";
  if (u.c_vid != null && u.s_vid != null) return `S:${u.s_vid} / C:${u.c_vid}`;
  if (u.s_vid != null) return `S:${u.s_vid}`;
  return "unknown";
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
  innerVlanId?: number | null
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
  return (
    <div className="iface-option">
      <div className="iface-option-head">
        <span className="iface-option-name">{iface.name}</span>
        {speed && <Tag bordered={false}>{speed}</Tag>}
        <Tag color={iface.oper_status === "up" ? "success" : "default"} bordered={false}>
          {iface.oper_status || "unknown"}
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
}: {
  iface?: DeviceInterface;
  vlanId?: number | null;
  accessMode?: string;
  innerVlanId?: number | null;
}) {
  if (!iface) return null;
  const speed = formatPortSpeed(iface.speed_mbps);
  const conflict = vlanConflict(iface.used_s_vids, vlanId, accessMode, innerVlanId);
  return (
    <div className="port-detail-panel">
      <div className="port-detail-title">
        <span>{iface.name}</span>
        {speed && <Tag>{speed}</Tag>}
        <Tag color={iface.oper_status === "up" ? "success" : "default"}>{iface.oper_status || "-"}</Tag>
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

export default function Circuits() {
  const { message, modal } = AntApp.useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const tenantFilter = searchParams.get("tenant");
  const selectedTenantId = tenantFilter ? Number(tenantFilter) : null;

  const [rows, setRows] = useState<Circuit[]>([]);
  const [overview, setOverview] = useState<TenantOverview | null>(null);
  const [activeSummary, setActiveSummary] = useState<TenantSummary | null>(null);
  const [tenantMap, setTenantMap] = useState<Record<number, string>>({});
  const tenantSearch = useTenantSearch(selectedTenantId);
  const [sites, setSites] = useState<Site[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const [modifyForm] = Form.useForm();
  const [modifyTarget, setModifyTarget] = useState<Circuit | null>(null);
  const [historyCircuit, setHistoryCircuit] = useState<Circuit | null>(null);
  const [history, setHistory] = useState<any>(null);
  const [diffText, setDiffText] = useState<Record<number, string>>({});

  async function load() {
    setLoading(true);
    const circuitUrl = selectedTenantId
      ? `/circuits?tenant_id=${selectedTenantId}`
      : "/circuits";
    const tasks: Array<{ key: string; req: Promise<{ data: unknown }> }> = [
      { key: "circuits", req: api.get<Circuit[]>(circuitUrl) },
      { key: "overview", req: api.get<TenantOverview>("/tenants/overview") },
      { key: "sites", req: api.get<Site[]>("/sites") },
      { key: "devices", req: api.get<Device[]>("/devices") },
    ];
    if (selectedTenantId) {
      tasks.push({
        key: "summary",
        req: api.get<TenantSummary>(`/tenants/${selectedTenantId}/summary`),
      });
    }
    const results = await Promise.allSettled(tasks.map((t) => t.req));
    const failed: string[] = [];
    let summaryLoaded: TenantSummary | null = null;
    results.forEach((result, idx) => {
      const key = tasks[idx].key;
      if (result.status === "rejected") {
        failed.push(key);
        return;
      }
      const data = result.value.data;
      switch (key) {
        case "circuits":
          setRows(data as Circuit[]);
          break;
        case "overview":
          setOverview(data as TenantOverview);
          break;
        case "sites":
          setSites(data as Site[]);
          break;
        case "devices":
          setDevices(data as Device[]);
          break;
        case "summary":
          summaryLoaded = data as TenantSummary;
          break;
      }
    });
    setActiveSummary(summaryLoaded);
    if (failed.length) {
      message.warning(`部分数据加载失败: ${failed.join(", ")}，请刷新页面重试`);
    }
    setLoading(false);
  }
  useEffect(() => {
    load();
  }, [selectedTenantId]);

  useEffect(() => {
    const missing = [...new Set(rows.map((r) => r.tenant_id))];
    missing.forEach((id) => {
      api.get<Tenant>(`/tenants/${id}`).then(({ data }) => {
        setTenantMap((m) => (m[id] ? m : { ...m, [id]: data.name }));
      });
    });
  }, [rows]);

  const tenantName = (id: number) => tenantMap[id] || `#${id}`;
  const deviceName = (id: number) => devices.find((d) => d.id === id)?.name || id;
  const siteName = (id?: number) => sites.find((s) => s.id === id)?.name || id;

  const stats = selectedTenantId && activeSummary
    ? {
        title: tenantSearch.options.find((o) => o.value === selectedTenantId)?.label || "当前客户",
        active: activeSummary.circuits_active,
        total: activeSummary.circuits_total,
        bandwidth: activeSummary.active_bandwidth_mbps,
        decommissioned: activeSummary.circuits_decommissioned,
        serviceTypes: Object.keys(activeSummary.by_service_type).length,
      }
    : overview
      ? {
          title: `全部客户 (${overview.tenants_total.toLocaleString()})`,
          active: overview.circuits_active,
          total: overview.circuits_total,
          bandwidth: overview.active_bandwidth_mbps,
          decommissioned: overview.circuits_decommissioned,
          serviceTypes: null as number | null,
        }
      : null;

  function setTenantFilter(id: number | null) {
    if (id) {
      setSearchParams({ tenant: String(id) });
    } else {
      setSearchParams({});
    }
  }

  async function removeCircuit(c: Circuit) {
    try {
      await api.delete(`/circuits/${c.id}`);
      message.success(`专线 ${c.code} 已删除`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "删除失败");
    }
  }

  async function onCreate() {
    const values = await form.validateFields();
    const payload = { ...values };
    if (typeof payload.ipt_nat_enabled === "boolean") {
      payload.ipt_nat_enabled = payload.ipt_nat_enabled ? 1 : 0;
    }
    if (payload.service_type !== "remote_ipt") {
      delete payload.egress_country;
      delete payload.egress_site_id;
      delete payload.ipt_nat_enabled;
    }
    const viaIds = (payload.via_hops || [])
      .map((h: { device_id?: number }) => h?.device_id)
      .filter(Boolean);
    payload.via_device_ids = viaIds;
    delete payload.via_hops;
    try {
      await api.post("/circuits", payload);
      message.success("专线已创建（草稿），可点击开通下发配置");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function runProvision(c: Circuit) {
    try {
      const { data } = await api.post(`/work-orders/provision/${c.id}`);
      if (data.status === "failed") {
        message.error(`开通工单 ${data.code} 失败（预检未通过）`);
      } else {
        message.success(`开通工单 ${data.code}: ${data.status}`);
      }
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "开通失败");
    }
  }

  async function provision(c: Circuit) {
    // Pre-flight compliance check before provisioning.
    const { data: v } = await api.get(`/circuits/${c.id}/validate`);
    if (!v.ok) {
      modal.confirm({
        title: `预检发现 ${v.errors} 个错误 / ${v.warnings} 个告警`,
        width: 560,
        content: (
          <div style={{ maxHeight: 320, overflow: "auto" }}>
            {v.issues.map((i: any, idx: number) => (
              <div key={idx} style={{ marginBottom: 4 }}>
                <Tag color={i.level === "error" ? "red" : "orange"}>{i.level}</Tag>
                <span>{i.message}</span>
              </div>
            ))}
            {v.errors > 0 && (
              <div style={{ color: "#cf1322", marginTop: 8 }}>
                存在错误，下发将被编排引擎阻断。
              </div>
            )}
          </div>
        ),
        okText: v.errors > 0 ? "仍尝试开通" : "继续开通",
        onOk: () => runProvision(c),
      });
      return;
    }
    runProvision(c);
  }

  async function decommission(c: Circuit) {
    try {
      const { data } = await api.post(
        `/work-orders/provision/${c.id}?wo_type=decommission`
      );
      message.success(`拆除工单 ${data.code}: ${data.status}`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "拆除失败");
    }
  }

  async function doModify() {
    if (!modifyTarget) return;
    const v = await modifyForm.validateFields();
    try {
      await api.patch(`/circuits/${modifyTarget.id}`, { bandwidth_mbps: v.bandwidth_mbps });
      const { data } = await api.post(
        `/work-orders/provision/${modifyTarget.id}?wo_type=modify`
      );
      message.success(`变更工单 ${data.code}: ${data.status}`);
      setModifyTarget(null);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "变更失败");
    }
  }

  async function probe(c: Circuit) {
    const hide = message.loading(`正在拨测 ${c.code} ...`, 0);
    try {
      const { data } = await api.post(`/circuits/${c.id}/probe`);
      hide();
      modal.info({
        title: `拨测结果 · ${data.circuit}`,
        width: 640,
        content: (
          <div>
            <div style={{ marginBottom: 8 }}>
              <Tag color={data.reachable ? "green" : "red"}>
                {data.reachable ? "可达" : "不可达"}
              </Tag>
              {data.rtt_ms != null && <Tag>RTT {data.rtt_ms} ms</Tag>}
              <Tag>抖动 {data.jitter_ms} ms</Tag>
              <Tag color={data.packet_loss_pct > 1 ? "red" : undefined}>
                丢包 {data.packet_loss_pct}%
              </Tag>
            </div>
            <Table
              size="small"
              rowKey="hop"
              pagination={false}
              dataSource={data.hops}
              columns={[
                { title: "跳", dataIndex: "hop", width: 50 },
                { title: "设备", dataIndex: "device" },
                { title: "厂商", dataIndex: "vendor", render: (v) => <Tag>{v}</Tag> },
                { title: "IP", dataIndex: "ip" },
                {
                  title: "RTT(ms)",
                  dataIndex: "rtt_ms",
                  render: (v) => (v == null ? "*" : v),
                },
                {
                  title: "状态",
                  dataIndex: "status",
                  render: (s) => (
                    <Tag color={s === "up" ? "green" : "red"}>{s}</Tag>
                  ),
                },
              ]}
            />
          </div>
        ),
      });
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || "拨测失败");
    }
  }

  async function openHistory(c: Circuit) {
    setHistoryCircuit(c);
    setDiffText({});
    const { data } = await api.get(`/circuits/${c.id}/config-history`);
    setHistory(data);
  }

  async function loadDiff(circuitId: number, deviceId: number) {
    const { data } = await api.get(
      `/circuits/${circuitId}/config-diff?device_id=${deviceId}`
    );
    setDiffText((prev) => ({ ...prev, [deviceId]: data.diff }));
  }

  async function preview(c: Circuit) {
    const wo = await api.post(`/work-orders`, { circuit_id: c.id, type: "provision" });
    const { data } = await api.get(`/work-orders/${wo.data.id}/preview`);
    modal.info({
      title: `配置预览 · ${c.code} (${c.name})`,
      ...configPreviewModalProps,
      content: (
        <div>
          {data.previews.map((p: any, i: number) => (
            <div key={i} className="config-preview-block">
              <div style={{ marginBottom: 8 }}>
                <Tag color="blue">{p.vendor.toUpperCase()}</Tag>
                <b>{p.device}</b> <Tag>{p.transport}</Tag>
              </div>
              <ConfigPreviewPre>{p.config}</ConfigPreviewPre>
            </div>
          ))}
        </div>
      ),
    });
  }

  return (
    <Card
      title="客户服务 · 专线"
      extra={
        <Space>
          <Button
            icon={<DownloadOutlined />}
            onClick={async () => {
              const url = selectedTenantId
                ? `/bulk/circuits/export?tenant_id=${selectedTenantId}`
                : "/bulk/circuits/export";
              const { data } = await api.get(url, { responseType: "text" });
              const blob = new Blob([data], { type: "text/csv" });
              const dl = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = dl;
              a.download = selectedTenantId ? `circuits-tenant-${selectedTenantId}.csv` : "circuits.csv";
              a.click();
              URL.revokeObjectURL(dl);
            }}
          >
            导出 CSV
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            新建专线
          </Button>
        </Space>
      }
    >
      <Space style={{ marginBottom: 16 }} wrap align="start">
        <TenantSearchSelect
          value={selectedTenantId ?? undefined}
          onChange={(v) => setTenantFilter(v ?? null)}
          options={tenantSearch.options}
          loading={tenantSearch.loading}
          onSearch={tenantSearch.onSearch}
          tenantTotal={tenantSearch.total}
        />
        {selectedTenantId && (
          <Button onClick={() => setTenantFilter(null)}>查看全部客户</Button>
        )}
        {overview && (
          <Typography.Text type="secondary">
            平台共 {overview.tenants_total.toLocaleString()} 个客户 · {overview.circuits_total.toLocaleString()} 条专线
          </Typography.Text>
        )}
      </Space>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={24} style={{ marginBottom: 8 }}>
            <Typography.Text strong>{stats.title}</Typography.Text>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="活跃专线" value={stats.active} suffix={`/ ${stats.total}`} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="活跃带宽" value={stats.bandwidth} suffix="Mbps" />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="已拆除" value={stats.decommissioned} valueStyle={{ color: "#8c8c8c" }} />
            </Card>
          </Col>
          {stats.serviceTypes != null && (
            <Col xs={12} md={6}>
              <Card size="small">
                <Statistic title="业务类型" value={stats.serviceTypes} suffix="种" />
              </Card>
            </Col>
          )}
        </Row>
      )}

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        expandable={{
          expandedRowRender: (r) => (
            <Descriptions size="small" column={3} bordered>
              <Descriptions.Item label="VNI">{r.vni}</Descriptions.Item>
              <Descriptions.Item label="VLAN">{r.vlan_id}</Descriptions.Item>
              <Descriptions.Item label="VRF">{r.vrf_name}</Descriptions.Item>
              <Descriptions.Item label="RD">{r.route_distinguisher}</Descriptions.Item>
              <Descriptions.Item label="RT">{r.route_target}</Descriptions.Item>
              <Descriptions.Item label="MTU">{r.mtu}</Descriptions.Item>
              {r.service_type === "remote_ipt" && (
                <>
                  <Descriptions.Item label="出口国家">{r.egress_country}</Descriptions.Item>
                  <Descriptions.Item label="出口站点">{siteName(r.egress_site_id)}</Descriptions.Item>
                  <Descriptions.Item label="公网 IP">{r.ipt_public_ip}</Descriptions.Item>
                  <Descriptions.Item label="NAT">
                    {r.ipt_nat_enabled ? "启用" : "关闭"}
                  </Descriptions.Item>
                </>
              )}
              <Descriptions.Item label="端点" span={3}>
                {r.endpoints.map((e) => (
                  <Tag key={e.id}>
                    {e.label}: {deviceName(e.device_id)} / {e.interface_name}
                    {e.access_mode ? ` · ${e.access_mode}` : ""}
                    {e.vlan_id ? ` vlan ${e.vlan_id}` : ""}
                    {e.inner_vlan_id ? `/${e.inner_vlan_id}` : ""}
                  </Tag>
                ))}
              </Descriptions.Item>
              {(r.path_mode === "explicit_sr" || (r.path_hops && r.path_hops.length > 0)) && (
                <Descriptions.Item label="SR 路径" span={3}>
                  <Tag color="purple">{r.path_mode || "auto"}</Tag>
                  {(r.path_hops || []).map((h) => (
                    <Tag key={h.sequence}>#{h.sequence + 1} {h.device_name || h.device_id}</Tag>
                  ))}
                  {r.segment_list && r.segment_list.length > 0 && (
                    <span style={{ marginLeft: 8, color: "#531dab" }}>
                      SID: {r.segment_list.join(" → ")}
                    </span>
                  )}
                </Descriptions.Item>
              )}
            </Descriptions>
          ),
        }}
        columns={[
          { title: "编码", dataIndex: "code" },
          { title: "名称", dataIndex: "name" },
          ...(!selectedTenantId
            ? [{ title: "租户", render: (_: unknown, r: Circuit) => tenantName(r.tenant_id) }]
            : []),
          {
            title: "业务类型",
            dataIndex: "service_type",
            render: (s: string) => (
              <Tag color={s === "remote_ipt" ? "purple" : "geekblue"}>
                {SERVICE_LABEL[s] || s}
              </Tag>
            ),
          },
          { title: "VNI", dataIndex: "vni" },
          {
            title: "带宽",
            dataIndex: "bandwidth_mbps",
            render: (b) => `${b} Mbps`,
          },
          { title: "SLA", dataIndex: "sla_target", render: (s) => s && <Tag>{s}%</Tag> },
          {
            title: "状态",
            dataIndex: "status",
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "操作",
            width: 280,
            render: (_, r) => (
              <Space wrap>
                <Tooltip
                  title={
                    r.status === "active"
                      ? "重新下发配置 (re-apply, dry-run)"
                      : "一键开通 (下发配置, dry-run)"
                  }
                >
                  <Button
                    size="small"
                    type="primary"
                    icon={<ThunderboltOutlined />}
                    onClick={() => provision(r)}
                  >
                    {r.status === "active" ? "重新下发" : "开通"}
                  </Button>
                </Tooltip>
                {r.status === "active" && (
                  <Tooltip title="变更带宽">
                    <Button
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => {
                        setModifyTarget(r);
                        modifyForm.setFieldsValue({ bandwidth_mbps: r.bandwidth_mbps });
                      }}
                    />
                  </Tooltip>
                )}
                <Tooltip title="预览各厂商配置">
                  <Button size="small" icon={<EyeOutlined />} onClick={() => preview(r)} />
                </Tooltip>
                {r.status === "active" && (
                  <Tooltip title="端到端拨测">
                    <Button
                      size="small"
                      icon={<RadarChartOutlined />}
                      onClick={() => probe(r)}
                    />
                  </Tooltip>
                )}
                <Tooltip title="配置历史与版本对比">
                  <Button size="small" icon={<HistoryOutlined />} onClick={() => openHistory(r)} />
                </Tooltip>
                {r.status !== "decommissioned" && r.status !== "draft" && (
                  <Popconfirm title="确认拆除该专线?" onConfirm={() => decommission(r)}>
                    <Button size="small" danger icon={<MinusCircleOutlined />} />
                  </Popconfirm>
                )}
                {DELETABLE.has(r.status) && (
                  <Popconfirm
                    title="确认永久删除该专线记录?"
                    description="仅删除系统记录，设备配置应已通过拆除工单清除"
                    onConfirm={() => removeCircuit(r)}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                )}
              </Space>
            ),
          },
        ]}
      />
      <CreateModal
        open={open}
        form={form}
        devices={devices}
        sites={sites}
        defaultTenantId={selectedTenantId}
        onOk={onCreate}
        onCancel={() => setOpen(false)}
        message={message}
      />
      <Modal
        title={`变更带宽 · ${modifyTarget?.code || ""}`}
        open={!!modifyTarget}
        onOk={doModify}
        onCancel={() => setModifyTarget(null)}
        okText="提交变更并下发"
      >
        <Form form={modifyForm} layout="vertical">
          <Form.Item
            name="bandwidth_mbps"
            label="新带宽 (Mbps)"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <div style={{ color: "#888", fontSize: 12 }}>
            变更将创建 MODIFY 工单并重新下发各厂商 QoS / 限速配置。
          </div>
        </Form>
      </Modal>

      <Drawer
        title={`配置历史 · ${historyCircuit?.code || ""}`}
        width={760}
        open={!!historyCircuit}
        onClose={() => setHistoryCircuit(null)}
      >
        {history && (
          <Collapse
            items={(history.devices || []).map((d: any) => ({
              key: d.device_id,
              label: (
                <span>
                  <b>{d.device}</b>{" "}
                  <Tag>{d.versions.length} 个版本</Tag>
                </span>
              ),
              children: (
                <>
                  <Button
                    size="small"
                    type="primary"
                    ghost
                    style={{ marginBottom: 8 }}
                    onClick={() => loadDiff(historyCircuit!.id, d.device_id)}
                  >
                    对比最近两个版本
                  </Button>
                  {diffText[d.device_id] && (
                    <pre className="config-pre">
                      {diffText[d.device_id].split("\n").map((line, i) => (
                        <div
                          key={i}
                          style={{
                            color: line.startsWith("+")
                              ? "#52c41a"
                              : line.startsWith("-")
                              ? "#ff7875"
                              : line.startsWith("@@")
                              ? "#1677ff"
                              : undefined,
                          }}
                        >
                          {line}
                        </div>
                      ))}
                    </pre>
                  )}
                  <Timeline
                    style={{ marginTop: 12 }}
                    items={d.versions
                      .slice()
                      .reverse()
                      .map((v: any) => ({
                        color: v.status.includes("fail") ? "red" : "blue",
                        children: (
                          <div>
                            <Tag>{v.work_order}</Tag>
                            <Tag color="geekblue">{v.operation}</Tag>
                            <Tag>{v.status}</Tag>
                            <span style={{ color: "#888", fontSize: 12 }}>
                              {v.created_at?.replace("T", " ").slice(0, 19)}
                            </span>
                            <pre className="config-pre" style={{ maxHeight: 180 }}>
                              {v.rendered_config}
                            </pre>
                          </div>
                        ),
                      }))}
                  />
                </>
              ),
            }))}
          />
        )}
      </Drawer>
    </Card>
  );
}

function CreateModal({
  open,
  form,
  devices: devicesProp,
  sites: sitesProp,
  defaultTenantId,
  onOk,
  onCancel,
  message,
}: any) {
  const [ifaceByDevice, setIfaceByDevice] = useState<Record<number, DeviceInterface[]>>({});
  const [pathPreview, setPathPreview] = useState<any>(null);
  const [formLoading, setFormLoading] = useState(false);
  const tenantSearch = useTenantSearch(open ? defaultTenantId : null);
  const offeringSearch = useOfferingSearch();
  const [devices, setDevices] = useState<Device[]>(devicesProp);
  const [sites, setSites] = useState<Site[]>(sitesProp);

  useEffect(() => {
    setDevices(devicesProp);
    setSites(sitesProp);
  }, [devicesProp, sitesProp]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    async function ensureFormData() {
      const needDevices = !devicesProp.length;
      const needSites = !sitesProp.length;
      if (!needDevices && !needSites) return;

      setFormLoading(true);
      try {
        const [dRes, sRes] = await Promise.allSettled([
          needDevices ? api.get<Device[]>("/devices") : Promise.resolve(null),
          needSites ? api.get<Site[]>("/sites") : Promise.resolve(null),
        ]);
        if (cancelled) return;
        if (dRes.status === "fulfilled" && dRes.value) setDevices(dRes.value.data);
        if (sRes.status === "fulfilled" && sRes.value) setSites(sRes.value.data);
        if (needDevices && dRes.status === "rejected") {
          message.error("表单数据加载失败，请刷新页面后重试");
        }
      } finally {
        if (!cancelled) setFormLoading(false);
      }
    }
    ensureFormData();
    return () => {
      cancelled = true;
    };
  }, [open, devicesProp, sitesProp, message]);

  function deviceLabel(d: Device) {
    const sid = d.sr_node_sid ? ` SID:${d.sr_node_sid}` : "";
    return `${d.name} (${d.vendor}/${d.overlay_tech})${sid}`;
  }

  async function previewPath() {
    const values = form.getFieldsValue();
    const endpointIds = (values.endpoints || [])
      .map((e: { device_id?: number }) => e?.device_id)
      .filter(Boolean);
    if (endpointIds.length < 2) {
      return message.warning("请先选择至少两个端点设备");
    }
    const viaIds = (values.via_hops || [])
      .map((h: { device_id?: number }) => h?.device_id)
      .filter(Boolean);
    const { data } = await api.post("/circuits/path/preview", {
      endpoint_device_ids: endpointIds,
      via_device_ids: viaIds,
      path_mode: values.path_mode || "auto",
    });
    setPathPreview(data);
  }

  useEffect(() => {
    if (open && defaultTenantId) {
      form.setFieldValue("tenant_id", defaultTenantId);
    }
  }, [open, defaultTenantId, form]);

  async function loadIfaces(deviceId: number, autoDiscover = true) {
    if (!deviceId) return;
    let { data } = await api.get<DeviceInterface[]>(`/devices/${deviceId}/interfaces`);
    if ((!data || data.length === 0) && autoDiscover) {
      const r = await api.post<DeviceInterface[]>(
        `/devices/${deviceId}/discover-interfaces`
      );
      data = r.data;
    }
    setIfaceByDevice((p) => ({ ...p, [deviceId]: data }));
  }

  async function discover(deviceId: number) {
    if (!deviceId) return message.warning("请先选择设备");
    const hide = message.loading("SNMP 发现 + S-VID 扫描...", 0);
    try {
      const { data } = await api.post<DeviceInterface[]>(
        `/devices/${deviceId}/discover-interfaces`
      );
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

  async function applyOffering(id: number) {
    const cached = offeringSearch.options.find((o) => o.value === id)?.offering;
    const o = cached || (await api.get<Offering>(`/offerings/${id}`)).data;
    form.setFieldsValue({
      service_type: o.service_type,
      bandwidth_mbps: o.bandwidth_mbps,
      sla_target: o.sla_target,
      cos: o.cos,
      mtu: o.mtu,
    });
  }
  return (
    <Modal
      title="新建专线"
      open={open}
      onOk={onOk}
      onCancel={onCancel}
      confirmLoading={formLoading}
      okText="创建"
      cancelText="取消"
      {...createCircuitModalProps}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          service_type: "l2vpn_evpn",
          bandwidth_mbps: 100,
          mtu: 9000,
          ipt_nat_enabled: true,
          path_mode: "auto",
          via_hops: [],
          endpoints: [{ label: "A" }, { label: "Z" }],
        }}
      >
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
          填写业务参数并配置 A/Z 接入端点；选择端口后可查看 S-VID 占用，避免 VLAN 冲突。
        </Typography.Text>

        <Form.Item name="offering_id" label="选择套餐 (可选)">
          <OfferingSearchSelect
            loading={offeringSearch.loading || formLoading}
            options={offeringSearch.options}
            onSearch={offeringSearch.onSearch}
            offeringTotal={offeringSearch.total}
            onChange={(v) => v && applyOffering(v as number)}
          />
        </Form.Item>

        <Row gutter={16}>
          <Col span={16}>
            <Form.Item name="name" label="名称" rules={[{ required: true }]}>
              <Input placeholder="例如 银行北京-上海二层专线" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="tenant_id" label="租户" rules={[{ required: true }]}>
              <TenantSearchSelect
                loading={tenantSearch.loading || formLoading}
                options={tenantSearch.options}
                onSearch={tenantSearch.onSearch}
                tenantTotal={tenantSearch.total}
                placeholder="搜索客户名称或编码"
              />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={10}>
            <Form.Item name="service_type" label="业务类型">
              <Select
                onChange={(v) => {
                  if (v === "remote_ipt") {
                    const eps = form.getFieldValue("endpoints") || [];
                    if (eps.length > 1) form.setFieldValue("endpoints", [eps[0]]);
                  }
                }}
                options={Object.entries(SERVICE_LABEL).map(([value, label]) => ({ value, label }))}
              />
            </Form.Item>
          </Col>
          <Col span={7}>
            <Form.Item name="bandwidth_mbps" label="带宽 (Mbps)">
              <InputNumber min={1} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col span={7}>
            <Form.Item name="sla_target" label="SLA (%)">
              <Input placeholder="99.95" />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item noStyle shouldUpdate={(p, c) => p.service_type !== c.service_type}>
          {({ getFieldValue }) =>
            getFieldValue("service_type") === "remote_ipt" ? (
              <div
                style={{
                  background: "#f9f0ff",
                  border: "1px solid #d3adf7",
                  borderRadius: 8,
                  padding: "12px 12px 0",
                  marginBottom: 12,
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 8, color: "#531dab" }}>
                  Remote IPT · 跨境公网出口
                </div>
                <div style={{ color: "#666", fontSize: 12, marginBottom: 8 }}>
                  客户通过专线接入本地端口，流量经 EVPN 隧道送至对端国家 PoP，
                  在边界网关 NAT 后使用当地公网 (IPT)。
                </div>
                <Space size="middle" style={{ display: "flex", flexWrap: "wrap" }}>
                  <Form.Item
                    name="egress_country"
                    label="公网出口国家/地区"
                    rules={[{ required: true, message: "请选择出口国家" }]}
                    style={{ minWidth: 200 }}
                  >
                    <Select options={EGRESS_COUNTRIES} placeholder="例如 US" />
                  </Form.Item>
                  <Form.Item
                    name="egress_site_id"
                    label="出口 PoP 站点"
                    rules={[{ required: true, message: "请选择出口站点" }]}
                    style={{ minWidth: 220 }}
                  >
                    <Select
                      showSearch
                      optionFilterProp="label"
                      options={sites.map((s: Site) => ({
                        value: s.id,
                        label: `${s.name} (${s.region || s.code})`,
                      }))}
                    />
                  </Form.Item>
                  <Form.Item name="ipt_nat_enabled" label="出口 NAT" valuePropName="checked">
                    <Switch checkedChildren="开" unCheckedChildren="关" />
                  </Form.Item>
                </Space>
              </div>
            ) : null
          }
        </Form.Item>

        <Divider orientation="left" style={{ margin: "8px 0 16px" }}>
          接入端点
        </Divider>
        <div style={{ marginBottom: 8, fontSize: 12, color: "#888" }}>
          图例：
          <Tag color="green" bordered={false} style={{ marginLeft: 8 }}>空闲</Tag>
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
                          <Space>
                            <Tag color={label === "A" ? "blue" : label === "Z" ? "purple" : "default"}>
                              端点 {label}
                            </Tag>
                          </Space>
                        }
                        extra={
                          fields.length > 1 ? (
                            <Button
                              type="text"
                              danger
                              size="small"
                              icon={<MinusCircleOutlined />}
                              onClick={() => remove(field.name)}
                            />
                          ) : null
                        }
                        style={{ marginBottom: 12 }}
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
                                options={devices.map((d: Device) => ({
                                  value: d.id,
                                  label: deviceLabel(d),
                                }))}
                              />
                            </Form.Item>
                          </Col>
                        </Row>

                        <Form.Item label="物理端口" required style={{ marginBottom: 8 }}>
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
                            <Button
                              icon={<RadarChartOutlined />}
                              disabled={!did}
                              onClick={() => discover(did!)}
                            >
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
                          />
                        )}

                        <Row gutter={[16, 0]} style={{ marginTop: 12 }}>
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
                              <InputNumber
                                placeholder="自动分配"
                                style={{ width: "100%" }}
                                min={1}
                                max={4094}
                              />
                            </Form.Item>
                          </Col>
                          {ep.access_mode === "qinq" && (
                            <Col xs={24} sm={12} md={8}>
                              <Form.Item name={[field.name, "inner_vlan_id"]} label="C-VID">
                                <InputNumber
                                  placeholder="内层 VLAN"
                                  style={{ width: "100%" }}
                                  min={1}
                                  max={4094}
                                />
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
              <Button
                type="dashed"
                block
                icon={<PlusOutlined />}
                onClick={() => add({ label: "", access_mode: "dot1q" })}
              >
                添加端点
              </Button>
            </>
          )}
        </Form.List>

        <Divider orientation="left" style={{ margin: "16px 0" }}>
          Underlay 路径
        </Divider>
        <Form.Item noStyle shouldUpdate>
          {({ getFieldValue }) => {
            const eps = getFieldValue("endpoints") || [];
            const epDevs = eps
              .map((e: { device_id?: number }) => devices.find((d: Device) => d.id === e?.device_id))
              .filter(Boolean) as Device[];
            const hasVxlan = epDevs.some((d) => d.overlay_tech === "vxlan_evpn");
            const allSr =
              epDevs.length >= 2 &&
              epDevs.every((d) => d.overlay_tech === "srmpls_evpn" && d.sr_node_sid);
            const srDevices = devices.filter(
              (d: Device) => d.overlay_tech === "srmpls_evpn" && d.sr_node_sid
            );
            const epIds = new Set(epDevs.map((d) => d.id));
            return (
              <div
                style={{
                  padding: 12,
                  border: "1px dashed #d9d9d9",
                  borderRadius: 8,
                }}
              >
                {hasVxlan && (
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 12 }}
                    message="BGP EVPN + OSPF 底层"
                    description="VXLAN 专线无法指定经由设备，流量按 OSPF/IGP 最短路径自动转发。"
                  />
                )}
                {allSr && (
                  <Alert
                    type="success"
                    showIcon
                    style={{ marginBottom: 12 }}
                    message="SR-MPLS 支持显式路径"
                    description="可指定经由的 P/PE 节点，控制器将下发 SR segment-list 策略。"
                  />
                )}
                <Form.Item name="path_mode" label="选路模式">
                  <Segmented
                    disabled={!allSr}
                    options={[
                      { label: "自动 (IS-IS SR 最短路径)", value: "auto" },
                      { label: "显式 SR 路径", value: "explicit_sr" },
                    ]}
                  />
                </Form.Item>
                <Form.Item noStyle shouldUpdate={(p, c) => p.path_mode !== c.path_mode}>
                  {() =>
                    getFieldValue("path_mode") === "explicit_sr" && allSr ? (
                      <>
                        <div style={{ fontWeight: 500, marginBottom: 8 }}>经由设备 (按顺序)</div>
                        <Form.List name="via_hops">
                          {(fields, { add, remove }) => (
                            <>
                              {fields.map((field) => (
                                <Space key={field.key} style={{ display: "flex", marginBottom: 8 }}>
                                  <Form.Item
                                    name={[field.name, "device_id"]}
                                    rules={[{ required: true, message: "选择经由设备" }]}
                                    noStyle
                                  >
                                    <Select
                                      style={{ width: 320 }}
                                      placeholder="SR 节点"
                                      showSearch
                                      optionFilterProp="label"
                                      options={srDevices
                                        .filter((d: Device) => !epIds.has(d.id))
                                        .map((d: Device) => ({
                                          value: d.id,
                                          label: deviceLabel(d),
                                        }))}
                                    />
                                  </Form.Item>
                                  <MinusCircleOutlined onClick={() => remove(field.name)} />
                                </Space>
                              ))}
                              <Button
                                type="dashed"
                                block
                                icon={<PlusOutlined />}
                                onClick={() => add({})}
                              >
                                添加经由跳
                              </Button>
                            </>
                          )}
                        </Form.List>
                      </>
                    ) : null
                  }
                </Form.Item>
                <Button onClick={previewPath} style={{ marginTop: 8 }}>
                  预览路径
                </Button>
                {pathPreview && (
                  <div style={{ marginTop: 12, fontSize: 12 }}>
                    {pathPreview.reason && (
                      <div style={{ color: "#666", marginBottom: 6 }}>{pathPreview.reason}</div>
                    )}
                    {pathPreview.hops?.map((h: any, i: number) => (
                      <Tag key={i} color={h.hop_type === "via" ? "purple" : "blue"}>
                        {h.name}
                        {h.sr_node_sid ? ` (SID ${h.sr_node_sid})` : ""}
                      </Tag>
                    ))}
                    {pathPreview.segment_list?.length > 0 && (
                      <div style={{ marginTop: 6, color: "#531dab" }}>
                        Segment-list: {pathPreview.segment_list.join(" → ")}
                      </div>
                    )}
                    {pathPreview.connectivity_errors?.length > 0 && (
                      <Alert
                        type="error"
                        style={{ marginTop: 8 }}
                        message={pathPreview.connectivity_errors.join("; ")}
                      />
                    )}
                  </div>
                )}
              </div>
            );
          }}
        </Form.Item>
      </Form>
    </Modal>
  );
}

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
  Tabs,
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
  LineChartOutlined,
  DeleteOutlined,
  SearchOutlined,
  ApartmentOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import type { Circuit, Device, Offering, Paginated, Site, Tenant } from "../api/types";
import { configPreviewModalProps, ConfigPreviewPre, createCircuitModalProps } from "../utils/configPreview";
import { formModalProps } from "../utils/formModal";
import { TenantSearchSelect, useTenantSearch } from "../components/TenantSearchSelect";
import OfferingSearchSelect, { useOfferingSearch } from "../components/OfferingSearchSelect";
import { buildListQuery, dataTableProps, tablePagination } from "../utils/table";
import { fetchAllPages } from "../utils/pagination";
import PageCard from "../components/PageCard";
import ListToolbar from "../components/ListToolbar";
import CircuitMonitorPanel from "../components/CircuitMonitorPanel";
import CircuitEndpointsEditor from "../components/CircuitEndpointsEditor";

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

export default function Circuits() {
  const { message, modal } = AntApp.useApp();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tenantFilter = searchParams.get("tenant");
  const selectedTenantId = tenantFilter ? Number(tenantFilter) : null;

  const [rows, setRows] = useState<Circuit[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [search, setSearch] = useState("");
  const [detailCache, setDetailCache] = useState<Record<number, Circuit>>({});
  const [overview, setOverview] = useState<TenantOverview | null>(null);
  const [activeSummary, setActiveSummary] = useState<TenantSummary | null>(null);
  const tenantSearch = useTenantSearch(selectedTenantId);
  const [sites, setSites] = useState<Site[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const [modifyForm] = Form.useForm();
  const [modifyTarget, setModifyTarget] = useState<Circuit | null>(null);
  const [editEndpointsTarget, setEditEndpointsTarget] = useState<Circuit | null>(null);
  const [editEndpointsForm] = Form.useForm();
  const [editEndpointsSaving, setEditEndpointsSaving] = useState(false);
  const [historyCircuit, setHistoryCircuit] = useState<Circuit | null>(null);
  const [history, setHistory] = useState<any>(null);
  const [diffText, setDiffText] = useState<Record<number, string>>({});

  async function loadCircuits(p = page, ps = pageSize, q = search) {
    setLoading(true);
    const circuitUrl = `/circuits${buildListQuery({
      tenant_id: selectedTenantId ?? undefined,
      page: p,
      page_size: ps,
      q: q || undefined,
    })}`;
    try {
      const { data } = await api.get<Paginated<Circuit>>(circuitUrl);
      setRows(data.items);
      setTotal(data.total);
    } catch {
      message.warning("专线列表加载失败，请刷新重试");
    } finally {
      setLoading(false);
    }
  }

  async function loadMeta() {
    const tasks: Array<{ key: string; req: Promise<{ data: unknown }> }> = [
      { key: "overview", req: api.get<TenantOverview>("/tenants/overview") },
      { key: "sites", req: api.get<Site[]>("/sites") },
      { key: "devices", req: fetchAllPages<Device>("/devices").then((items) => ({ data: items })) },
    ];
    const results = await Promise.allSettled(tasks.map((t) => t.req));
    const failed: string[] = [];
    results.forEach((result, idx) => {
      const key = tasks[idx].key;
      if (result.status === "rejected") {
        failed.push(key);
        return;
      }
      const data = result.value.data;
      switch (key) {
        case "overview":
          setOverview(data as TenantOverview);
          break;
        case "sites":
          setSites(data as Site[]);
          break;
        case "devices":
          setDevices(data as Device[]);
          break;
      }
    });
    if (failed.length) {
      message.warning(`部分数据加载失败: ${failed.join(", ")}，请刷新页面重试`);
    }
  }

  async function loadTenantSummary() {
    if (!selectedTenantId) {
      setActiveSummary(null);
      return;
    }
    try {
      const { data } = await api.get<TenantSummary>(`/tenants/${selectedTenantId}/summary`);
      setActiveSummary(data);
    } catch {
      setActiveSummary(null);
    }
  }

  async function loadCircuitDetail(id: number) {
    if (detailCache[id]) return detailCache[id];
    const { data } = await api.get<Circuit>(`/circuits/${id}`);
    setDetailCache((prev) => ({ ...prev, [id]: data }));
    return data;
  }
  useEffect(() => {
    setPage(1);
    setDetailCache({});
  }, [selectedTenantId]);

  useEffect(() => {
    loadCircuits(page, pageSize, search);
  }, [selectedTenantId, page, pageSize]);

  useEffect(() => {
    loadMeta();
  }, []);

  useEffect(() => {
    if (!editEndpointsTarget || devices.length) return;
    fetchAllPages<Device>("/devices").then(setDevices).catch(() => {});
  }, [editEndpointsTarget, devices.length]);

  useEffect(() => {
    loadTenantSummary();
  }, [selectedTenantId]);

  const tenantName = (id: number) =>
    tenantSearch.options.find((o) => o.value === id)?.label?.split(" · ")[0] || `#${id}`;
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
      loadCircuits();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "删除失败");
    }
  }

  async function onCreate() {
    const values = await form.validateFields();
    const payload = { ...values };
    if (payload.vni === undefined || payload.vni === null || payload.vni === "") {
      delete payload.vni;
    }
    if (!payload.vsi_name || !String(payload.vsi_name).trim()) {
      delete payload.vsi_name;
    } else {
      payload.vsi_name = String(payload.vsi_name).trim();
    }
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
      loadCircuits();
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
      loadCircuits();
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
      loadCircuits();
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
      loadCircuits();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "变更失败");
    }
  }

  function openEditEndpoints(circuit: Circuit, detail?: Circuit) {
    const d = detail || detailCache[circuit.id] || circuit;
    setEditEndpointsTarget(d);
    editEndpointsForm.setFieldsValue({
      endpoints: (d.endpoints || []).map((e) => ({
        label: e.label,
        device_id: e.device_id,
        interface_name: e.interface_name,
        access_mode: e.access_mode || "dot1q",
        vlan_id: e.vlan_id,
        inner_vlan_id: e.inner_vlan_id,
      })),
    });
  }

  async function saveEndpointsAndProvision() {
    if (!editEndpointsTarget) return;
    const values = await editEndpointsForm.validateFields();
    const endpoints = (values.endpoints || []).map(
      ({ label, device_id, interface_name, access_mode, vlan_id, inner_vlan_id }: Record<string, unknown>) => ({
        label,
        device_id,
        interface_name,
        access_mode: access_mode || "dot1q",
        ...(vlan_id != null && vlan_id !== "" ? { vlan_id } : {}),
        ...(inner_vlan_id != null && inner_vlan_id !== "" ? { inner_vlan_id } : {}),
      }),
    );
    const minEps = editEndpointsTarget.service_type === "remote_ipt" ? 1 : 2;
    if (endpoints.length < minEps) {
      message.warning(`至少需要 ${minEps} 个端点`);
      return;
    }
    setEditEndpointsSaving(true);
    const circuitId = editEndpointsTarget.id;
    try {
      await api.put(`/circuits/${circuitId}/endpoints`, { endpoints });
      const woType =
        editEndpointsTarget.status === "active" || editEndpointsTarget.status === "degraded"
          ? "modify"
          : "provision";
      const { data } = await api.post(
        `/work-orders/provision/${circuitId}?wo_type=${woType}`,
      );
      message.success(
        woType === "modify"
          ? `端点已更新，变更工单 ${data.code}: ${data.status}`
          : `端点已更新，开通工单 ${data.code}: ${data.status}`,
      );
      setEditEndpointsTarget(null);
      editEndpointsForm.resetFields();
      setDetailCache((prev) => {
        const next = { ...prev };
        delete next[circuitId];
        return next;
      });
      loadCircuits();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "端点更新失败");
    } finally {
      setEditEndpointsSaving(false);
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
    <PageCard
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
      <ListToolbar
        summary={`当前 ${total.toLocaleString()} 条专线${total > pageSize ? " · 已分页" : ""}`}
        left={
          <>
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
            <Input.Search
              allowClear
              placeholder="搜索专线编码或名称"
              style={{ width: 260 }}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onSearch={() => {
                setPage(1);
                loadCircuits(1, pageSize, search);
              }}
              enterButton={<SearchOutlined />}
            />
          </>
        }
        right={
          overview ? (
            <Typography.Text type="secondary">
              平台 {overview.tenants_total.toLocaleString()} 客户 · {overview.circuits_total.toLocaleString()} 专线
            </Typography.Text>
          ) : undefined
        }
      />

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
        {...dataTableProps(1280)}
        pagination={tablePagination(total, page, pageSize, (p, ps) => {
          setPage(p);
          setPageSize(ps);
        })}
        expandable={{
          onExpand: (expanded, r) => {
            if (expanded) loadCircuitDetail(r.id);
          },
          expandedRowRender: (r) => {
            const detail = detailCache[r.id] || r;
            return (
              <Tabs
                size="small"
                items={[
                  {
                    key: "detail",
                    label: "参数详情",
                    children: (
                      <Descriptions size="small" column={3} bordered>
                        <Descriptions.Item label="VNI">{detail.vni}</Descriptions.Item>
                        <Descriptions.Item label="VSI">{detail.vsi_name || "-"}</Descriptions.Item>
                        <Descriptions.Item label="VLAN">{detail.vlan_id}</Descriptions.Item>
                        <Descriptions.Item label="VRF">{detail.vrf_name}</Descriptions.Item>
                        <Descriptions.Item label="RD">{detail.route_distinguisher}</Descriptions.Item>
                        <Descriptions.Item label="RT">{detail.route_target}</Descriptions.Item>
                        <Descriptions.Item label="MTU">{detail.mtu}</Descriptions.Item>
                        {detail.service_type === "remote_ipt" && (
                          <>
                            <Descriptions.Item label="出口国家">{detail.egress_country}</Descriptions.Item>
                            <Descriptions.Item label="出口站点">{siteName(detail.egress_site_id)}</Descriptions.Item>
                            <Descriptions.Item label="公网 IP">{detail.ipt_public_ip}</Descriptions.Item>
                            <Descriptions.Item label="NAT">
                              {detail.ipt_nat_enabled ? "启用" : "关闭"}
                            </Descriptions.Item>
                          </>
                        )}
                        <Descriptions.Item label="端点" span={3}>
                          <Space direction="vertical" size={8} style={{ width: "100%" }}>
                            <Space wrap>
                              {detail.endpoints.map((e) => (
                                <Tag key={e.id}>
                                  {e.label}: {deviceName(e.device_id)} / {e.interface_name}
                                  {e.access_mode ? ` · ${e.access_mode}` : ""}
                                  {e.vlan_id ? ` vlan ${e.vlan_id}` : ""}
                                  {e.inner_vlan_id ? `/${e.inner_vlan_id}` : ""}
                                </Tag>
                              ))}
                            </Space>
                            {r.status !== "decommissioned" && (
                              <Button
                                size="small"
                                type="link"
                                icon={<EditOutlined />}
                                style={{ padding: 0, height: "auto" }}
                                onClick={() => openEditEndpoints(r, detail)}
                              >
                                修改端点并重新下发
                              </Button>
                            )}
                          </Space>
                        </Descriptions.Item>
                        {(detail.path_mode === "explicit_sr" || (detail.path_hops && detail.path_hops.length > 0)) && (
                          <Descriptions.Item label="SR 路径" span={3}>
                            <Tag color="purple">{detail.path_mode || "auto"}</Tag>
                            {(detail.path_hops || []).map((h) => (
                              <Tag key={h.sequence}>#{h.sequence + 1} {h.device_name || h.device_id}</Tag>
                            ))}
                            {detail.segment_list && detail.segment_list.length > 0 && (
                              <span style={{ marginLeft: 8, color: "#531dab" }}>
                                SID: {detail.segment_list.join(" → ")}
                              </span>
                            )}
                          </Descriptions.Item>
                        )}
                      </Descriptions>
                    ),
                  },
                  {
                    key: "monitor",
                    label: "流量监控",
                    children: (
                      r.status === "active" ? (
                        <CircuitMonitorPanel circuitId={r.id} compact pollSec={0} />
                      ) : (
                        <Alert type="info" showIcon message="专线激活后可查看 SNMP 流量、95 值、时延与中断记录" />
                      )
                    ),
                  },
                ]}
              />
            );
          },
        }}
        columns={[
          { title: "编码", dataIndex: "code", width: 120, ellipsis: true },
          { title: "名称", dataIndex: "name", width: 160, ellipsis: true },
          ...(!selectedTenantId
            ? [{ title: "租户", width: 100, ellipsis: true, render: (_: unknown, r: Circuit) => tenantName(r.tenant_id) }]
            : []),
          {
            title: "业务类型",
            dataIndex: "service_type",
            width: 120,
            render: (s: string) => (
              <Tag color={s === "remote_ipt" ? "purple" : "geekblue"}>
                {SERVICE_LABEL[s] || s}
              </Tag>
            ),
          },
          { title: "VNI", dataIndex: "vni", width: 80 },
          {
            title: "VSI",
            dataIndex: "vsi_name",
            width: 130,
            ellipsis: true,
            render: (v) => v || "—",
          },
          {
            title: "带宽",
            dataIndex: "bandwidth_mbps",
            width: 100,
            render: (b) => `${b} Mbps`,
          },
          {
            title: "SLA",
            dataIndex: "sla_target",
            width: 80,
            render: (s) => (s ? <Tag>{s}%</Tag> : "—"),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 90,
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "操作",
            width: 300,
            className: "table-actions",
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
                {r.status !== "decommissioned" && (
                  <Tooltip title="修改接入端点 (设备/端口/VLAN)">
                    <Button
                      size="small"
                      icon={<ApartmentOutlined />}
                      onClick={async () => {
                        const detail = await loadCircuitDetail(r.id);
                        openEditEndpoints(r, detail);
                      }}
                    />
                  </Tooltip>
                )}
                <Tooltip title="预览各厂商配置">
                  <Button size="small" icon={<EyeOutlined />} onClick={() => preview(r)} />
                </Tooltip>
                {r.status === "active" && (
                  <Tooltip title="流量 / 95 / 时延 / 中断监控">
                    <Button
                      size="small"
                      icon={<LineChartOutlined />}
                      onClick={() => navigate(`/monitoring?circuit=${r.id}`)}
                    />
                  </Tooltip>
                )}
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
        {...formModalProps}
        width={480}
      >
        <Form form={modifyForm} layout="vertical" className="app-form">
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

      <Modal
        title={editEndpointsTarget ? `修改端点 · ${editEndpointsTarget.code}` : "修改端点"}
        open={!!editEndpointsTarget}
        onOk={saveEndpointsAndProvision}
        onCancel={() => {
          setEditEndpointsTarget(null);
          editEndpointsForm.resetFields();
        }}
        confirmLoading={editEndpointsSaving}
        okText={
          editEndpointsTarget?.status === "active" || editEndpointsTarget?.status === "degraded"
            ? "保存并重新下发"
            : "保存并开通"
        }
        cancelText="取消"
        {...formModalProps}
        width={960}
        wrapClassName="app-form-modal create-circuit-modal"
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="修改接入端点"
          description="可更换设备、物理端口、封装模式与 S-VID。保存后将创建变更/开通工单并重新下发各端设备配置。"
        />
        <Form form={editEndpointsForm} layout="vertical" className="app-form">
          <CircuitEndpointsEditor
            form={editEndpointsForm}
            devices={devices}
            preloadDeviceIds={editEndpointsTarget?.endpoints.map((e) => e.device_id) || []}
            minEndpoints={editEndpointsTarget?.service_type === "remote_ipt" ? 1 : 2}
          />
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
    </PageCard>
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
      setFormLoading(true);
      try {
        const [deviceRows, siteRows] = await Promise.all([
          fetchAllPages<Device>("/devices"),
          sitesProp.length
            ? Promise.resolve(sitesProp)
            : api.get<Site[]>("/sites").then((r) => r.data),
        ]);
        if (cancelled) return;
        setDevices(deviceRows);
        if (!sitesProp.length) setSites(siteRows);
      } catch {
        if (!cancelled) message.error("表单数据加载失败，请刷新页面后重试");
      } finally {
        if (!cancelled) setFormLoading(false);
      }
    }
    ensureFormData();
    return () => {
      cancelled = true;
    };
  }, [open, sitesProp, message]);

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

  function deviceLabel(d: Device) {
    const sid = d.sr_node_sid ? ` SID:${d.sr_node_sid}` : "";
    return `${d.name} (${d.vendor}/${d.overlay_tech})${sid}`;
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
        className="app-form"
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

        <Collapse
          ghost
          items={[
            {
              key: "evpn",
              label: "EVPN 标识（VNI / VSI · 留空自动编排）",
              children: (
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name="vni"
                      label="VNI"
                      extra="留空则平台自动分配，不可与已有专线重复"
                      rules={[
                        {
                          type: "number",
                          min: 1,
                          max: 16777215,
                          message: "VNI 范围 1–16777215",
                        },
                      ]}
                    >
                      <InputNumber min={1} max={16777215} style={{ width: "100%" }} placeholder="自动分配" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name="vsi_name"
                      label="VSI 名称"
                      extra="H3C 等设备 VSI 实例名，留空则按编码自动生成"
                      rules={[
                        { max: 63, message: "最长 63 字符" },
                        {
                          pattern: /^[A-Za-z0-9_-]*$/,
                          message: "仅允许字母、数字、下划线、连字符",
                        },
                      ]}
                    >
                      <Input placeholder="例如 vsi_cir_ab12cd" />
                    </Form.Item>
                  </Col>
                </Row>
              ),
            },
          ]}
        />

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
                <Row gutter={16}>
                  <Col xs={24} sm={8}>
                    <Form.Item
                      name="egress_country"
                      label="公网出口国家/地区"
                      rules={[{ required: true, message: "请选择出口国家" }]}
                    >
                      <Select options={EGRESS_COUNTRIES} placeholder="例如 US" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} sm={10}>
                    <Form.Item
                      name="egress_site_id"
                      label="出口 PoP 站点"
                      rules={[{ required: true, message: "请选择出口站点" }]}
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
                  </Col>
                  <Col xs={24} sm={6}>
                    <Form.Item name="ipt_nat_enabled" label="出口 NAT" valuePropName="checked">
                      <Switch checkedChildren="开" unCheckedChildren="关" />
                    </Form.Item>
                  </Col>
                </Row>
              </div>
            ) : null
          }
        </Form.Item>

        <Divider orientation="left" style={{ margin: "8px 0 16px" }}>
          接入端点
        </Divider>
        <CircuitEndpointsEditor form={form} devices={devices} formLoading={formLoading} minEndpoints={1} />

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

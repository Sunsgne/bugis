import { useEffect, useRef, useState } from "react";
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
  Dropdown,
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
  MoreOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import type { Circuit, Device, Paginated, ProvisionResult, Site, Tenant, WorkOrder } from "../api/types";
import { configPreviewModalProps, ConfigPreviewPre, createCircuitModalProps } from "../utils/configPreview";
import { formModalProps } from "../utils/formModal";
import { TenantSearchSelect, useTenantSearch } from "../components/TenantSearchSelect";
import { buildListQuery, dataTableProps, tablePagination } from "../utils/table";
import { fetchAllPages } from "../utils/pagination";
import PageCard from "../components/PageCard";
import ListToolbar from "../components/ListToolbar";
import CircuitExpandDetail from "../components/CircuitExpandDetail";
import CircuitForwardingPathPanel from "../components/CircuitForwardingPathPanel";
import CircuitAlarmThresholdFields from "../components/CircuitAlarmThresholdFields";
import { formatOperStatus } from "../utils/networkDisplay";
import CircuitMonitorPanel from "../components/CircuitMonitorPanel";
import CircuitEndpointsEditor from "../components/CircuitEndpointsEditor";
import ProvisionFeedbackModal from "../components/ProvisionFeedbackModal";
import ProvisionProgressDock from "../components/ProvisionProgressDock";
import { CIRCUIT_STATUS, SERVICE_TYPE, statusMeta } from "../constants/statusLabels";
import { useTc } from "@/i18n/useTc";
import { useTranslation } from "react-i18next";

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

type CircuitConfirmAction = "decommission" | "delete";

export default function Circuits() {
  const { tc } = useTc();
  const { t } = useTranslation();
  const { message, modal } = AntApp.useApp();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tenantFilter = searchParams.get("tenant");
  const circuitDeepLink = searchParams.get("circuit");
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
  const [provisionCircuit, setProvisionCircuit] = useState<Circuit | null>(null);
  const [provisionLoading, setProvisionLoading] = useState(false);
  const [provisionResult, setProvisionResult] = useState<ProvisionResult | null>(null);
  const [provisionError, setProvisionError] = useState<string | null>(null);
  const [provisioningId, setProvisioningId] = useState<number | null>(null);
  const [provisionType, setProvisionType] = useState<string>("provision");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [circuitConfirm, setCircuitConfirm] = useState<{
    circuit: Circuit;
    action: CircuitConfirmAction;
  } | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [expandedRowKeys, setExpandedRowKeys] = useState<React.Key[]>([]);
  const handledCircuitLink = useRef<number | null>(null);

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
      message.warning(tc("专线列表加载失败，请刷新重试"));
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
      message.warning(tc(`部分数据加载失败: ${failed.join(", ")}，请刷新页面重试`));
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
    const id = Number(circuitDeepLink);
    if (!circuitDeepLink || !id || Number.isNaN(id)) {
      handledCircuitLink.current = null;
      return;
    }
    if (handledCircuitLink.current === id) return;

    let cancelled = false;

    (async () => {
      try {
        const { data: circuit } = await api.get<Circuit>(`/circuits/${id}`);
        if (cancelled) return;

        const tenantParam = searchParams.get("tenant");
        if (tenantParam && Number(tenantParam) !== circuit.tenant_id) {
          setSearchParams({ circuit: String(id) });
          handledCircuitLink.current = null;
          return;
        }

        if (!rows.some((r) => r.id === id)) {
          const { data: pageData } = await api.get<Paginated<Circuit>>(
            `/circuits${buildListQuery({
              tenant_id: selectedTenantId ?? undefined,
              page: 1,
              page_size: pageSize,
              q: circuit.code,
            })}`,
          );
          if (cancelled) return;
          setRows(pageData.items);
          setTotal(pageData.total);
          setPage(1);
          setSearch(circuit.code);
        }

        await loadCircuitDetail(id);
        if (cancelled) return;
        setExpandedRowKeys([id]);
        handledCircuitLink.current = id;

        window.setTimeout(() => {
          document
            .querySelector(`tr[data-row-key="${id}"]`)
            ?.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 150);
      } catch {
        if (!cancelled) {
          message.warning(tc("无法打开该专线，可能不存在或无权查看"));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [circuitDeepLink, selectedTenantId, pageSize, searchParams, setSearchParams, message]);

  useEffect(() => {
    setPage(1);
    setDetailCache({});
  }, [selectedTenantId]);

  useEffect(() => {
    if (circuitDeepLink) return;
    loadCircuits(page, pageSize, search);
  }, [selectedTenantId, page, pageSize, circuitDeepLink]);

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
        title: tenantSearch.options.find((o) => o.value === selectedTenantId)?.label || tc("当前客户"),
        active: activeSummary.circuits_active,
        total: activeSummary.circuits_total,
        bandwidth: activeSummary.active_bandwidth_mbps,
        decommissioned: activeSummary.circuits_decommissioned,
        serviceTypes: Object.keys(activeSummary.by_service_type).length,
      }
    : overview
      ? {
          title: t("circuits.allTenants", { count: overview.tenants_total.toLocaleString() }),
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
    setDeletingId(c.id);
    try {
      await api.delete(`/circuits/${c.id}`);
      setRows((prev) => prev.filter((row) => row.id !== c.id));
      setTotal((prev) => Math.max(0, prev - 1));
      setExpandedRowKeys((prev) => prev.filter((k) => k !== c.id));
      setDetailCache((prev) => {
        const next = { ...prev };
        delete next[c.id];
        return next;
      });
      message.success(tc(`专线 ${c.code} 已删除`));
      loadTenantSummary();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("删除失败"));
      loadCircuits();
    } finally {
      setDeletingId(null);
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
    for (const key of [
      "alarm_latency_ms",
      "alarm_packet_loss_pct",
      "alarm_utilization_pct",
      "alarm_health_score_min",
    ] as const) {
      if (payload[key] === undefined || payload[key] === null || payload[key] === "") {
        delete payload[key];
      }
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
      message.success(tc("专线已创建（草稿），可点击开通下发配置"));
      setOpen(false);
      form.resetFields();
      loadCircuits();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("创建失败"));
    }
  }

  function closeProvisionFeedback() {
    setProvisionCircuit(null);
    setProvisionResult(null);
    setProvisionError(null);
    setProvisionLoading(false);
    setProvisioningId(null);
    setDetailsOpen(false);
  }

  async function executeProvision(
    c: Circuit,
    woType = "provision",
    body?: { previous_endpoints?: Array<Record<string, unknown>> },
  ) {
    setProvisionCircuit(c);
    setProvisionType(woType);
    setProvisionLoading(true);
    setProvisionResult(null);
    setProvisionError(null);
    setProvisioningId(c.id);
    const failLabel = woType === "decommission" ? "拆除失败" : "下发失败";
    try {
      const url =
        woType === "provision"
          ? `/work-orders/provision/${c.id}`
          : `/work-orders/provision/${c.id}?wo_type=${woType}`;
      const { data } = await api.post<ProvisionResult>(url, body ?? undefined);
      setProvisionResult(data);
      // Async mode: the work order is queued (scheduled) / running — poll the
      // work order until it reaches a terminal state so the staged progress
      // view animates through to completion.
      const terminal = ["completed", "failed", "cancelled", "rolled_back"];
      if (!terminal.includes(data.status)) {
        await pollWorkOrderProgress(data, terminal);
      } else if (data.status === "failed") {
        message.error(tc(`工单 ${data.code} 执行失败，请查看下发详情`));
      }
      setDetailCache((prev) => {
        const next = { ...prev };
        delete next[c.id];
        return next;
      });
      loadCircuits();
    } catch (e: any) {
      setProvisionError(e?.response?.data?.detail || failLabel);
    } finally {
      setProvisionLoading(false);
      setProvisioningId(null);
    }
  }

  async function pollWorkOrderProgress(base: ProvisionResult, terminal: string[]) {
    setProvisionLoading(false);
    let pollErrors = 0;
    for (let i = 0; i < 120; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      let wo: WorkOrder;
      try {
        const { data } = await api.get<WorkOrder>(`/work-orders/${base.id}`);
        wo = data;
        pollErrors = 0;
      } catch {
        pollErrors += 1;
        if (pollErrors >= 5) {
          message.error(tc("工单状态轮询失败，请刷新页面查看进度"));
          return;
        }
        continue;
      }
      const merged: ProvisionResult = { ...base, ...wo };
      setProvisionResult(merged);
      if (terminal.includes(wo.status)) {
        try {
          const { data: circ } = await api.get<Circuit>(`/circuits/${base.circuit_id}`);
          setProvisionResult({ ...merged, circuit_status: circ.status });
        } catch {
          /* keep merged */
        }
        if (wo.status === "failed") {
          message.error(tc(`工单 ${wo.code} 执行失败，请查看下发详情`));
        }
        loadCircuits();
        return;
      }
    }
  }

  async function runProvision(c: Circuit) {
    await executeProvision(c);
  }

  async function provision(c: Circuit) {
    // Pre-flight compliance check before provisioning.
    const { data: v } = await api.get(`/circuits/${c.id}/validate`);
    if (!v.ok) {
      if (v.errors > 0) {
        modal.warning({
          title: `预检发现 ${v.errors} 个错误`,
          width: 560,
          content: (
            <div style={{ maxHeight: 320, overflow: "auto" }}>
              {v.issues.map((i: any, idx: number) => (
                <div key={idx} style={{ marginBottom: 4 }}>
                  <Tag color={i.level === "error" ? "red" : "orange"}>{i.level}</Tag>
                  <span>{i.message}</span>
                </div>
              ))}
              <div style={{ color: "#cf1322", marginTop: 8 }}>
                存在错误，编排引擎将阻断下发，请先修复后再开通。
              </div>
            </div>
          ),
        });
        return;
      }
      modal.confirm({
        title: `预检发现 ${v.warnings} 个告警`,
        width: 560,
        content: (
          <div style={{ maxHeight: 320, overflow: "auto" }}>
            {v.issues.map((i: any, idx: number) => (
              <div key={idx} style={{ marginBottom: 4 }}>
                <Tag color="orange">{i.level}</Tag>
                <span>{i.message}</span>
              </div>
            ))}
          </div>
        ),
        okText: "继续开通",
        onOk: () => runProvision(c),
      });
      return;
    }
    runProvision(c);
  }

  async function decommission(c: Circuit) {
    // Route teardown through the same staged feedback modal so operators get a
    // visual, step-by-step view of the recovery (安全校验 → 配置回收 → 结果确认).
    await executeProvision(c, "decommission");
  }

  async function doModify() {
    if (!modifyTarget) return;
    const v = await modifyForm.validateFields();
    try {
      const patch: Record<string, unknown> = {
        latency_probe_enabled: v.latency_probe_enabled !== false,
        alarm_latency_ms: v.alarm_latency_ms ?? null,
        alarm_packet_loss_pct: v.alarm_packet_loss_pct ?? null,
        alarm_utilization_pct: v.alarm_utilization_pct ?? null,
        alarm_health_score_min: v.alarm_health_score_min ?? null,
      };
      const bwChanged = v.bandwidth_mbps !== modifyTarget.bandwidth_mbps;
      if (bwChanged) {
        patch.bandwidth_mbps = v.bandwidth_mbps;
      }
      await api.patch(`/circuits/${modifyTarget.id}`, patch);
      if (bwChanged) {
        const { data } = await api.post(
          `/work-orders/provision/${modifyTarget.id}?wo_type=modify`
        );
        message.success(tc(`变更工单 ${data.code}: ${data.status}`));
      } else {
        message.success(tc("告警参数已保存"));
      }
      setModifyTarget(null);
      loadCircuits();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("变更失败"));
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
      message.warning(tc(`至少需要 ${minEps} 个端点`));
      return;
    }
    const adopted = !!editEndpointsTarget.adopted;
    const previousEndpoints = (editEndpointsTarget.endpoints || []).map((e) => ({
      label: e.label,
      device_id: e.device_id,
      interface_name: e.interface_name,
      access_mode: e.access_mode || "dot1q",
      ...(e.vlan_id != null ? { vlan_id: e.vlan_id } : {}),
      ...(e.inner_vlan_id != null ? { inner_vlan_id: e.inner_vlan_id } : {}),
    }));
    setEditEndpointsSaving(true);
    const circuitId = editEndpointsTarget.id;
    const circuitCode = editEndpointsTarget.code;
    try {
      const { data } = await api.put<Circuit>(`/circuits/${circuitId}/endpoints`, { endpoints });
      setEditEndpointsTarget(null);
      editEndpointsForm.resetFields();
      if (adopted) {
        message.success(tc(`端点已登记 · ${data.endpoints?.length ?? endpoints.length} 个节点（未向设备下发配置）`));
        loadCircuits();
        return;
      }
      const woType =
        editEndpointsTarget.status === "active" || editEndpointsTarget.status === "degraded"
          ? "modify"
          : "provision";
      await executeProvision(
        { ...editEndpointsTarget, id: circuitId, code: circuitCode },
        woType,
        woType === "modify" ? { previous_endpoints: previousEndpoints } : undefined,
      );
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("端点更新失败"));
    } finally {
      setEditEndpointsSaving(false);
    }
  }

  async function probe(c: Circuit) {
    const hide = message.loading(`正在拨测 ${c.code} ...`, 0);
    try {
      const { data } = await api.post(`/circuits/${c.id}/probe`);
      hide();

      const modeLabel =
        data.mode === "live"
          ? { text: "实测", color: "blue" as const }
          : { text: "模拟", color: "default" as const };
      const methodLabels: Record<string, string> = {
        simulated: "模拟估算",
        simulated_inactive: "非激活 · 模拟",
        h3c_vsi_mac: "H3C VSI MAC Ping",
        vni_ping: "VNI Ping",
        fabric_loopback: "Fabric 逐跳 Ping",
        underlay_ip: "Underlay IP Ping",
      };
      const probeMethod = data.probe_method || data.service_plane?.method || "—";
      const sp = data.service_plane;
      const fabric = data.fabric;

      modal.info({
        title: `拨测结果 · ${data.circuit}`,
        width: 720,
        content: (
          <div>
            <div style={{ marginBottom: 12 }}>
              <Tag color={modeLabel.color}>{modeLabel.text}</Tag>
              <Tag>{methodLabels[probeMethod] || probeMethod}</Tag>
              {data.path_mode && (
                <Tag color="geekblue">
                  路径 {data.path_mode === "explicit_sr" ? "SR 显式" : "IGP 自动"}
                </Tag>
              )}
              <Tag color={data.reachable ? "green" : "red"}>
                {data.reachable ? "可达" : "不可达"}
              </Tag>
            </div>
            <div style={{ marginBottom: 12 }}>
              {data.rtt_ms != null && <Tag>端到端 RTT {data.rtt_ms} ms</Tag>}
              {data.jitter_ms != null && <Tag>抖动 {data.jitter_ms} ms</Tag>}
              {data.packet_loss_pct != null && (
                <Tag color={data.packet_loss_pct > 1 ? "red" : undefined}>
                  丢包 {data.packet_loss_pct}%
                </Tag>
              )}
            </div>
            {data.path_reason && (
              <div style={{ marginBottom: 12, color: "var(--text-secondary, #666)", fontSize: 12 }}>
                {data.path_reason}
              </div>
            )}
            {sp && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>业务面 (A→Z)</div>
                <Space wrap size={[8, 4]}>
                  {sp.source_device && sp.target_device && (
                    <Tag>
                      {sp.source_device} → {sp.target_device}
                    </Tag>
                  )}
                  {sp.vsi_name && <Tag>VSI {sp.vsi_name}</Tag>}
                  {sp.vni != null && <Tag>VNI {sp.vni}</Tag>}
                  {sp.remote_mac && <Tag>MAC {sp.remote_mac}</Tag>}
                  {sp.samples != null && <Tag>{sp.samples} 次采样</Tag>}
                </Space>
              </div>
            )}
            {fabric && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>Fabric 逐跳</div>
                <Tag color={fabric.reachable ? "green" : "red"}>
                  {fabric.reachable ? "Underlay 可达" : "Underlay 异常"}
                </Tag>
                {fabric.samples_per_hop != null && (
                  <Tag>每跳 {fabric.samples_per_hop} 次 Ping</Tag>
                )}
              </div>
            )}
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
                  title: "探测目标",
                  dataIndex: "target",
                  render: (v) => v || "—",
                },
                {
                  title: "段 RTT(ms)",
                  dataIndex: "segment_rtt_ms",
                  render: (v) => (v == null ? "—" : v),
                },
                {
                  title: "累计 RTT(ms)",
                  dataIndex: "rtt_ms",
                  render: (v) => (v == null ? "—" : v),
                },
                {
                  title: "状态",
                  dataIndex: "status",
                  render: (s) => (
                    <Tag color={s === "up" ? "green" : "red"}>{formatOperStatus(s)}</Tag>
                  ),
                },
              ]}
            />
          </div>
        ),
      });
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || tc("拨测失败"));
    }
  }

  async function openHistory(c: Circuit) {
    try {
      const { data } = await api.get(`/circuits/${c.id}/config-history`);
      setHistoryCircuit(c);
      setDiffText({});
      setHistory(data);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("加载配置历史失败"));
    }
  }

  async function loadDiff(circuitId: number, deviceId: number) {
    try {
      const { data } = await api.get(
        `/circuits/${circuitId}/config-diff?device_id=${deviceId}`
      );
      setDiffText((prev) => ({ ...prev, [deviceId]: data.diff }));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("加载配置差异失败"));
    }
  }

  async function preview(c: Circuit) {
    let data: { previews: any[] };
    try {
      // Non-persisting render — does NOT create a work order.
      ({ data } = await api.get(`/circuits/${c.id}/preview`));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("配置预览失败"));
      return;
    }
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
      title={tc("客户服务 · 专线")}
      extra={
        <Space>
          <Button
            icon={<DownloadOutlined />}
            onClick={async () => {
              try {
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
              } catch (e: any) {
                message.error(e?.response?.data?.detail || tc("导出失败"));
              }
            }}
          >
            {tc("导出 CSV")}
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            {tc("新建专线")}
          </Button>
        </Space>
      }
    >
      <ListToolbar
        summary={t("circuits.summary", {
          total: total.toLocaleString(),
          suffix: total > pageSize ? t("circuits.paginatedSuffix") : "",
        })}
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
              <Button onClick={() => setTenantFilter(null)}>{tc("查看全部客户")}</Button>
            )}
            <Input.Search
              allowClear
              placeholder={tc("搜索专线编码或名称")}
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
              {t("circuits.platformStats", {
                tenants: overview.tenants_total.toLocaleString(),
                circuits: overview.circuits_total.toLocaleString(),
              })}
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
              <Statistic title={tc("活跃专线")} value={stats.active} suffix={`/ ${stats.total}`} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title={tc("活跃带宽")} value={stats.bandwidth} suffix="Mbps" />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title={tc("已拆除")} value={stats.decommissioned} valueStyle={{ color: "#8c8c8c" }} />
            </Card>
          </Col>
          {stats.serviceTypes != null && (
            <Col xs={12} md={6}>
              <Card size="small">
                <Statistic title={tc("业务类型")} value={stats.serviceTypes} suffix={tc("种")} />
              </Card>
            </Col>
          )}
        </Row>
      )}


      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        {...dataTableProps(selectedTenantId ? 1180 : 1080, rows.length > 0)}
        pagination={tablePagination(total, page, pageSize, (p, ps) => {
          setPage(p);
          setPageSize(ps);
        })}
        expandable={{
          expandedRowKeys,
          onExpandedRowsChange: (keys) => setExpandedRowKeys([...keys]),
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
                    label: tc("参数详情"),
                    children: (
                      <CircuitExpandDetail
                        detail={detail}
                        deviceName={deviceName}
                        siteName={siteName}
                        canEditEndpoints={r.status !== "decommissioned"}
                        onEditEndpoints={() => openEditEndpoints(r, detail)}
                      />
                    ),
                  },
                  {
                    key: "forwarding-path",
                    label: tc("转发路径"),
                    children: (
                      <CircuitForwardingPathPanel circuitId={r.id} circuitCode={detail.code || r.code} />
                    ),
                  },
                  {
                    key: "monitor",
                    label: tc("流量监控"),
                    children: (
                      r.status === "active" ? (
                        <CircuitMonitorPanel
                          circuitId={r.id}
                          compact
                          pollSec={0}
                          latencyProbeEnabled={detail.latency_probe_enabled !== false}
                        />
                      ) : (
                        <Alert type="info" showIcon message={tc("专线激活后可查看 SNMP 流量、95 值、时延与中断记录")} />
                      )
                    ),
                  },
                ]}
              />
            );
          },
        }}
        columns={[
          { title: tc("编码"), dataIndex: "code", width: 120, ellipsis: true },
          { title: tc("名称"), dataIndex: "name", width: 160, ellipsis: true },
          ...(!selectedTenantId
            ? [{ title: tc("客户"), width: 100, ellipsis: true, render: (_: unknown, r: Circuit) => tenantName(r.tenant_id) }]
            : []),
          {
            title: tc("业务类型"),
            dataIndex: "service_type",
            width: 120,
            render: (s: string) => (
              <Tag color={s === "remote_ipt" ? "purple" : "geekblue"}>
                {SERVICE_LABEL[s] || SERVICE_TYPE[s] || s}
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
            title: tc("带宽"),
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
            title: tc("状态"),
            dataIndex: "status",
            width: 88,
            render: (s) => {
              const m = statusMeta(CIRCUIT_STATUS, s);
              return <Tag color={m.color}>{m.label}</Tag>;
            },
          },
          {
            title: tc("操作"),
            key: "actions",
            width: 184,
            fixed: "right",
            align: "right",
            className: "table-actions-col",
            render: (_, r) => {
              // Primary action stays inline; everything else collapses into a
              // "更多" dropdown to keep the column compact and consistent.
              const moreItems = [
                r.status === "active" && {
                  key: "modify",
                  icon: <EditOutlined />,
                  label: tc("变更参数 / 告警"),
                  onClick: async () => {
                    const detail = await loadCircuitDetail(r.id);
                    setModifyTarget(detail);
                    modifyForm.setFieldsValue({
                      bandwidth_mbps: detail.bandwidth_mbps,
                      latency_probe_enabled: detail.latency_probe_enabled !== false,
                      alarm_latency_ms: detail.alarm_latency_ms,
                      alarm_packet_loss_pct: detail.alarm_packet_loss_pct,
                      alarm_utilization_pct: detail.alarm_utilization_pct,
                      alarm_health_score_min: detail.alarm_health_score_min,
                    });
                  },
                },
                r.status !== "decommissioned" && {
                  key: "endpoints",
                  icon: <ApartmentOutlined />,
                  label: tc("修改接入端点"),
                  onClick: async () => {
                    const detail = await loadCircuitDetail(r.id);
                    openEditEndpoints(r, detail);
                  },
                },
                { key: "preview", icon: <EyeOutlined />, label: tc("预览各厂商配置"), onClick: () => preview(r) },
                r.status === "active" && {
                  key: "monitor",
                  icon: <LineChartOutlined />,
                  label: tc("流量 / 95 / 监控"),
                  onClick: () => navigate(`/monitoring?circuit=${r.id}`),
                },
                r.status === "active" &&
                  r.latency_probe_enabled !== false && {
                  key: "probe",
                  icon: <RadarChartOutlined />,
                  label: tc("端到端拨测"),
                  onClick: () => probe(r),
                },
                { key: "history", icon: <HistoryOutlined />, label: tc("配置历史与对比"), onClick: () => openHistory(r) },
                (r.status !== "decommissioned" && r.status !== "draft") && {
                  key: "decommission",
                  icon: <MinusCircleOutlined />,
                  danger: true,
                  label: tc("拆除专线"),
                  onClick: () => setCircuitConfirm({ circuit: r, action: "decommission" }),
                },
                DELETABLE.has(r.status) && {
                  key: "delete",
                  icon: <DeleteOutlined />,
                  danger: true,
                  label: tc("永久删除记录"),
                  onClick: () => setCircuitConfirm({ circuit: r, action: "delete" }),
                },
              ].filter(Boolean) as { key: string }[];

              return (
                <Space size={4} className="table-actions">
                  {r.status !== "decommissioned" && (
                    r.status === "provisioning" ? (
                      <Button
                        size="small"
                        type="primary"
                        icon={<ThunderboltOutlined />}
                        loading
                        disabled
                      >
                        {tc("开通中")}
                      </Button>
                    ) : (
                    <Popconfirm
                      title={
                        r.status === "active"
                          ? tc("确认重新下发该专线?")
                          : tc("确认开通该专线?")
                      }
                      placement="topRight"
                      okText={tc("确定")}
                      cancelText={tc("取消")}
                      onConfirm={() => provision(r)}
                    >
                      <Tooltip
                        title={
                          r.status === "active"
                            ? tc("重新下发配置 (re-apply)")
                            : tc("一键开通 (下发配置)")
                        }
                      >
                        <Button
                          size="small"
                          type="primary"
                          icon={<ThunderboltOutlined />}
                          loading={provisioningId === r.id}
                        >
                          {r.status === "active" ? tc("重新下发") : tc("开通")}
                        </Button>
                      </Tooltip>
                    </Popconfirm>
                    )
                  )}
                  {moreItems.length > 0 && (
                    <Popconfirm
                      title={
                        circuitConfirm?.action === "delete"
                          ? tc("确认永久删除该专线记录?")
                          : tc("确认拆除该专线?")
                      }
                      placement="topRight"
                      okText={tc("确定")}
                      cancelText={tc("取消")}
                      okButtonProps={{
                        loading:
                          circuitConfirm?.action === "delete" &&
                          deletingId === circuitConfirm.circuit.id,
                      }}
                      open={circuitConfirm?.circuit.id === r.id}
                      onOpenChange={(nextOpen) => {
                        if (!nextOpen && circuitConfirm?.circuit.id === r.id) {
                          setCircuitConfirm(null);
                        }
                      }}
                      onConfirm={async () => {
                        const target = circuitConfirm;
                        setCircuitConfirm(null);
                        if (!target) return;
                        if (target.action === "delete") {
                          await removeCircuit(target.circuit);
                        } else {
                          await decommission(target.circuit);
                        }
                      }}
                    >
                      <Dropdown menu={{ items: moreItems }} trigger={["click"]}>
                        <Button size="small" icon={<MoreOutlined />}>{tc("更多")}</Button>
                      </Dropdown>
                    </Popconfirm>
                  )}
                </Space>
              );
            },
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
        title={`变更参数 · ${modifyTarget?.code || ""}`}
        open={!!modifyTarget}
        onOk={doModify}
        onCancel={() => setModifyTarget(null)}
        okText="保存"
        {...formModalProps}
        width={640}
      >
        <Form form={modifyForm} layout="vertical" className="app-form">
          <Form.Item
            name="bandwidth_mbps"
            label="带宽 (Mbps)"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <div className="form-hint-block" style={{ marginBottom: 16 }}>
            仅当带宽发生变化时会创建 MODIFY 工单并重新下发 QoS / 限速配置；仅修改告警参数不会触发下发。
          </div>
          <CircuitAlarmThresholdFields />
        </Form>
      </Modal>

      <Modal
        title={
          editEndpointsTarget
            ? editEndpointsTarget.adopted
              ? `添加/登记端点 · ${editEndpointsTarget.code}`
              : `修改端点 · ${editEndpointsTarget.code}`
            : "修改端点"
        }
        open={!!editEndpointsTarget}
        onOk={saveEndpointsAndProvision}
        onCancel={() => {
          setEditEndpointsTarget(null);
          editEndpointsForm.resetFields();
        }}
        confirmLoading={editEndpointsSaving}
        okText={
          editEndpointsTarget?.adopted
            ? "保存（不下发）"
            : editEndpointsTarget?.status === "active" || editEndpointsTarget?.status === "degraded"
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
          message={editEndpointsTarget?.adopted ? "纳管专线 · 登记接入端点" : "修改接入端点"}
          description={
            editEndpointsTarget?.adopted
              ? "从现网选择额外接入节点并登记到平台，不会向设备下发任何配置。新增端点须为设备上已存在的 S-VID 绑定，且 VNI/VSI 须与本专线一致。"
              : "可更换设备、物理端口、封装模式与 S-VID。保存后将先拆除变更前的旧接入配置，再下发新端点配置（创建变更/开通工单）。"
          }
        />
        <Form form={editEndpointsForm} layout="vertical" className="app-form">
          <CircuitEndpointsEditor
            form={editEndpointsForm}
            devices={devices}
            preloadDeviceIds={editEndpointsTarget?.endpoints.map((e) => e.device_id) || []}
            minEndpoints={editEndpointsTarget?.service_type === "remote_ipt" ? 1 : 2}
            excludeCircuitCode={editEndpointsTarget?.code}
            adoptMode={!!editEndpointsTarget?.adopted}
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
                              ? "#ff8c1a"
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

      <ProvisionProgressDock
        circuit={provisionCircuit}
        woType={provisionType}
        loading={provisionLoading}
        result={provisionResult}
        error={provisionError}
        onOpenDetails={() => setDetailsOpen(true)}
        onClose={closeProvisionFeedback}
      />

      <ProvisionFeedbackModal
        open={detailsOpen}
        circuit={provisionCircuit}
        woType={provisionType}
        loading={provisionLoading}
        result={provisionResult}
        error={provisionError}
        onClose={() => setDetailsOpen(false)}
      />
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
  const { tc } = useTc();
  const [pathPreview, setPathPreview] = useState<any>(null);
  const [formLoading, setFormLoading] = useState(false);
  const tenantSearch = useTenantSearch(open ? defaultTenantId : null);
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
        if (!cancelled) message.error(tc("表单数据加载失败，请刷新页面后重试"));
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
      return message.warning(tc("请先选择至少两个端点设备"));
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

  return (
    <Modal
      title={tc("新建专线")}
      open={open}
      onOk={onOk}
      onCancel={onCancel}
      confirmLoading={formLoading}
      okText={tc("创建")}
      cancelText={tc("取消")}
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
          latency_probe_enabled: true,
          via_hops: [],
          endpoints: [{ label: "A" }, { label: "Z" }],
        }}
      >
        <Typography.Text type="secondary" className="app-form-intro">
          {tc("填写业务参数并配置 A/Z 接入端点；选择端口后可查看 S-VID 占用，避免 VLAN 冲突。")}
        </Typography.Text>

        <Row gutter={16}>
          <Col span={16}>
            <Form.Item name="name" label={tc("名称")} rules={[{ required: true }]}>
              <Input placeholder={tc("例如 银行北京-上海二层专线")} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="tenant_id" label={tc("客户")} rules={[{ required: true }]}>
              <TenantSearchSelect
                loading={tenantSearch.loading || formLoading}
                options={tenantSearch.options}
                onSearch={tenantSearch.onSearch}
                tenantTotal={tenantSearch.total}
                placeholder={tc("搜索客户名称或编码")}
              />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={10}>
            <Form.Item name="service_type" label={tc("业务类型")}>
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
            <Form.Item name="bandwidth_mbps" label={tc("带宽 (Mbps)")}>
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
              label: tc("EVPN 标识（VNI / VSI · 留空自动编排）"),
              children: (
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name="vni"
                      label="VNI"
                      extra={tc("留空则平台自动分配，不可与已有专线重复")}
                      rules={[
                        {
                          type: "number",
                          min: 1,
                          max: 16777215,
                          message: tc("VNI 范围 1–16777215"),
                        },
                      ]}
                    >
                      <InputNumber min={1} max={16777215} style={{ width: "100%" }} placeholder={tc("自动分配")} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name="vsi_name"
                      label={tc("VSI 名称")}
                      extra={tc("H3C 等设备 VSI 实例名，留空则按编码自动生成")}
                      rules={[
                        { max: 63, message: tc("最长 63 字符") },
                        {
                          pattern: /^[A-Za-z0-9_-]*$/,
                          message: tc("仅允许字母、数字、下划线、连字符"),
                        },
                      ]}
                    >
                      <Input placeholder={tc("例如 vsi_cir_ab12cd")} />
                    </Form.Item>
                  </Col>
                </Row>
              ),
            },
            {
              key: "alarm",
              label: tc("SLA 告警阈值（可选 · 留空继承平台默认）"),
              children: <CircuitAlarmThresholdFields />,
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

        <Divider plain>{tc("接入端点")}</Divider>
        <Form.Item noStyle shouldUpdate={(p, c) => p.service_type !== c.service_type}>
          {({ getFieldValue }) => (
            <CircuitEndpointsEditor
              form={form}
              devices={devices}
              formLoading={formLoading}
              minEndpoints={getFieldValue("service_type") === "remote_ipt" ? 1 : 2}
            />
          )}
        </Form.Item>

        <Divider plain>{tc("Underlay 路径")}</Divider>
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
              <div className="form-section-box">
                {hasVxlan && (
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 12 }}
                    message={tc("BGP EVPN + OSPF 底层")}
                    description={tc("VXLAN 专线无法指定经由设备，流量按 OSPF/IGP 最短路径自动转发。")}
                  />
                )}
                {allSr && (
                  <Alert
                    type="success"
                    showIcon
                    style={{ marginBottom: 12 }}
                    message={tc("SR-MPLS 支持显式路径")}
                    description={tc("可指定经由的 P/PE 节点，控制器将下发 SR segment-list 策略。")}
                  />
                )}
                <Form.Item name="path_mode" label={tc("选路模式")}>
                  <Segmented
                    disabled={!allSr}
                    options={[
                      { label: tc("自动 (IS-IS SR 最短路径)"), value: "auto" },
                      { label: tc("显式 SR 路径"), value: "explicit_sr" },
                    ]}
                  />
                </Form.Item>
                <Form.Item noStyle shouldUpdate={(p, c) => p.path_mode !== c.path_mode}>
                  {() =>
                    getFieldValue("path_mode") === "explicit_sr" && allSr ? (
                      <>
                        <div style={{ fontWeight: 500, marginBottom: 8 }}>{tc("经由设备 (按顺序)")}</div>
                        <Form.List name="via_hops">
                          {(fields, { add, remove }) => (
                            <>
                              {fields.map((field) => (
                                <Space key={field.key} style={{ display: "flex", marginBottom: 8 }}>
                                  <Form.Item
                                    name={[field.name, "device_id"]}
                                    rules={[{ required: true, message: tc("选择经由设备") }]}
                                    noStyle
                                  >
                                    <Select
                                      style={{ width: 320 }}
                                      placeholder={tc("SR 节点")}
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
                                {tc("添加经由跳")}
                              </Button>
                            </>
                          )}
                        </Form.List>
                      </>
                    ) : null
                  }
                </Form.Item>
                <Button onClick={previewPath} style={{ marginTop: 8 }}>
                  {tc("预览路径")}
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

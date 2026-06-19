import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Input,
  Popconfirm,
  Progress,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined, SearchOutlined, SyncOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import type { Device, LinkUsage, SiteCapacity } from "../api/types";
import BackboneLinkModal from "../components/BackboneLinkModal";
import InterfaceNameCell from "../components/InterfaceNameCell";
import { utilColor } from "../charts/options";
import { fetchAllPages } from "../utils/pagination";
import { useTc } from "@/i18n/useTc";
import { dataTableProps, TABLE_SCROLL } from "../utils/table";

const LINK_TYPE_LABEL: Record<string, string> = {
  dci: "跨站点 DCI",
  intra_dc: "站内互联",
  access: "接入",
  uplink: "上联",
};

function gbps(mbps: number) {
  return Math.round((mbps || 0) / 1000);
}

function fmtBw(mbps?: number) {
  if (!mbps) return "—";
  return mbps >= 1000 ? `${Math.round(mbps / 1000)} Gbps` : `${mbps} Mbps`;
}

function siteRouteLabel(r: LinkUsage) {
  const a = r.site_a_code || r.site_a || "—";
  const z = r.site_z_code || r.site_z || "—";
  return `${a} → ${z}`;
}

function siteRouteKey(r: LinkUsage) {
  return `${r.site_a_id ?? ""}:${r.site_z_id ?? ""}`;
}

function formatPeakAt(iso?: string | null) {
  if (!iso) return "—";
  return dayjs(iso).format("YYYY-MM-DD HH:mm:ss");
}

function utilizationTooltip(r: LinkUsage, pct: number) {
  const peakRx = r.peak_rx_mbps ?? 0;
  const peakTx = r.peak_tx_mbps ?? 0;
  const peakTotal = r.peak_traffic_mbps ?? peakRx + peakTx;
  const lines = [
    `峰值利用率 ${Math.round(pct)}%`,
    `峰值带宽 Rx ${fmtBw(peakRx)} / Tx ${fmtBw(peakTx)} · 合计 ${fmtBw(peakTotal)}`,
    `合同带宽 ${fmtBw(r.capacity_mbps)}`,
    `采样时间 ${formatPeakAt(r.peak_at)}`,
  ];
  if (r.traffic_mbps != null && r.traffic_mbps > 0) {
    lines.push(`当前流量 ${fmtBw(r.traffic_mbps)}`);
  }
  if (r.effective_alarm_utilization_pct != null) {
    lines.push(`告警阈值 ${r.effective_alarm_utilization_pct}%`);
  }
  return (
    <div style={{ lineHeight: 1.6 }}>
      {lines.map((line) => (
        <div key={line}>{line}</div>
      ))}
    </div>
  );
}

export default function Capacity() {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [sites, setSites] = useState<SiteCapacity[]>([]);
  const [links, setLinks] = useState<LinkUsage[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [siteSearch, setSiteSearch] = useState("");
  const [linkSearch, setLinkSearch] = useState("");
  const [supplierFilter, setSupplierFilter] = useState<string | undefined>();
  const [siteRouteFilter, setSiteRouteFilter] = useState<string | undefined>();

  // Devices are only needed by the "配置骨干链路" drawer — load lazily on open,
  // never on the 10s capacity poll (which would refetch the whole fleet).
  const [devices, setDevices] = useState<Device[]>([]);
  const [devicesLoaded, setDevicesLoaded] = useState(false);
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [editingLink, setEditingLink] = useState<LinkUsage | null>(null);

  async function load(showSpinner = false) {
    if (showSpinner) setLoading(true);
    try {
      const [s, l] = await Promise.all([
        api.get<SiteCapacity[]>("/capacity/sites"),
        api.get<LinkUsage[]>("/capacity/links/usage"),
      ]);
      setSites(s.data);
      setLinks(l.data);
    } catch {
      message.error(tc('容量数据加载失败，请稍后重试'));
    } finally {
      if (showSpinner) setLoading(false);
    }
  }

  async function openLinkModal(link?: LinkUsage) {
    setEditingLink(link ?? null);
    setLinkModalOpen(true);
    if (!devicesLoaded) {
      try {
        const d = await fetchAllPages<Device>("/devices");
        setDevices(d);
        setDevicesLoaded(true);
      } catch {
        message.error(tc('设备列表加载失败'));
      }
    }
  }

  function closeLinkModal() {
    setLinkModalOpen(false);
    setEditingLink(null);
  }

  async function syncBandwidth() {
    setSyncing(true);
    try {
      await api.post("/capacity/links/sync-bandwidth");
      await load();
      message.success(tc('已从端口描述同步合同带宽'));
    } catch {
      message.error(tc('同步合同带宽失败'));
    } finally {
      setSyncing(false);
    }
  }

  async function deleteLink(linkId: number) {
    try {
      await api.delete(`/capacity/links/${linkId}`);
      message.success(tc('骨干链路已删除'));
      await load();
    } catch {
      message.error(tc('删除骨干链路失败'));
    }
  }

  useEffect(() => {
    load(true);
    const t = setInterval(() => load(false), 10000);
    return () => clearInterval(t);
  }, []);

  const totalCap = useMemo(() => sites.reduce((a, s) => a + s.capacity_mbps, 0), [sites]);
  const totalUsed = useMemo(() => sites.reduce((a, s) => a + s.used_mbps, 0), [sites]);
  const utilPct = totalCap ? Math.round((totalUsed / totalCap) * 1000) / 10 : 0;

  const filteredSites = useMemo(() => {
    const q = siteSearch.trim().toLowerCase();
    if (!q) return sites;
    return sites.filter(
      (s) => s.site.toLowerCase().includes(q) || s.code.toLowerCase().includes(q),
    );
  }, [sites, siteSearch]);

  const filteredLinks = useMemo(() => {
    const q = linkSearch.trim().toLowerCase();
    return links.filter((l) => {
      if (supplierFilter && (l.supplier || "") !== supplierFilter) return false;
      if (siteRouteFilter && siteRouteKey(l) !== siteRouteFilter) return false;
      if (!q) return true;
      const route = siteRouteLabel(l).toLowerCase();
      return (
        l.name.toLowerCase().includes(q) ||
        l.device_a.toLowerCase().includes(q) ||
        l.device_z.toLowerCase().includes(q) ||
        (l.supplier || "").toLowerCase().includes(q) ||
        route.includes(q) ||
        (l.site_a || "").toLowerCase().includes(q) ||
        (l.site_z || "").toLowerCase().includes(q)
      );
    });
  }, [links, linkSearch, supplierFilter, siteRouteFilter]);

  const supplierOptions = useMemo(() => {
    const set = new Set<string>();
    for (const l of links) {
      const s = l.supplier?.trim();
      if (s) set.add(s);
    }
    return Array.from(set).sort().map((v) => ({ value: v, label: v }));
  }, [links]);

  const siteRouteOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const l of links) {
      const key = siteRouteKey(l);
      if (!l.site_a_id && !l.site_z_id) continue;
      if (!seen.has(key)) seen.set(key, siteRouteLabel(l));
    }
    return Array.from(seen.entries())
      .sort((a, b) => a[1].localeCompare(b[1], "zh"))
      .map(([value, label]) => ({ value, label }));
  }, [links]);

  const pagination = {
    defaultPageSize: 20,
    showSizeChanger: true,
    pageSizeOptions: ["20", "50", "100", "200"],
    showTotal: (total: number) => `共 ${total} 项`,
  };

  return (
    <div className="capacity-page">
      <div className="capacity-kpi-row">
        <Card className="capacity-kpi-card">
          <Statistic title={tc('Fabric 总容量')} value={gbps(totalCap)} suffix="Gbps" />
        </Card>
        <Card className="capacity-kpi-card">
          <Statistic
            title={tc('已分配带宽')}
            value={gbps(totalUsed)}
            suffix="Gbps"
            valueStyle={{ color: "#ff6600" }}
          />
        </Card>
        <Card className="capacity-kpi-card capacity-kpi-util">
          <div className="capacity-kpi-util-label">{tc('全域带宽分配率')}</div>
          <Progress percent={utilPct} strokeColor={utilColor(utilPct)} strokeWidth={10} />
        </Card>
      </div>

      <Card
        className="capacity-section-card"
        title={`Fabric 站点容量（${sites.length}）`}
        extra={
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder={tc('搜索站点名称 / 编码')}
            value={siteSearch}
            onChange={(e) => setSiteSearch(e.target.value)}
            style={{ width: 240 }}
          />
        }
      >
        <Table<SiteCapacity>
          {...dataTableProps(TABLE_SCROLL.lg)}
          size="small"
          className="data-table capacity-data-table"
          rowKey="site_id"
          loading={loading}
          dataSource={filteredSites}
          pagination={pagination}
          scroll={{ x: 720 }}
          locale={{ emptyText: siteSearch ? "无匹配站点" : "暂无站点容量数据" }}
          columns={[
            {
              title: tc('站点'),
              dataIndex: "site",
              fixed: "left",
              width: 260,
              sorter: (a, b) => a.code.localeCompare(b.code),
              render: (_: unknown, r) => (
                <Space direction="vertical" size={0}>
                  <span style={{ fontWeight: 600 }}>{r.code}</span>
                  <span style={{ color: "#8a9099", fontSize: 12 }}>{r.site}</span>
                </Space>
              ),
            },
            {
              title: tc('设备'),
              dataIndex: "devices",
              width: 90,
              align: "right",
              sorter: (a, b) => a.devices - b.devices,
              render: (v: number) => `${v} 台`,
            },
            {
              title: tc('已分配 / 总容量'),
              key: "cap",
              width: 180,
              align: "right",
              sorter: (a, b) => a.used_mbps - b.used_mbps,
              render: (_: unknown, r) => `${gbps(r.used_mbps)} / ${gbps(r.capacity_mbps)} Gbps`,
            },
            {
              title: tc('带宽分配率'),
              dataIndex: "utilization_pct",
              width: 260,
              defaultSortOrder: "descend",
              sorter: (a, b) => a.utilization_pct - b.utilization_pct,
              render: (v: number) => (
                <Progress
                  percent={v}
                  size="small"
                  strokeColor={utilColor(v)}
                  format={(p) => `${p}%`}
                />
              ),
            },
          ]}
        />
      </Card>

      <Card
        className="capacity-section-card capacity-backbone-card"
        title={`骨干链路 · 利用率（${links.length}）`}
        extra={
          <Space wrap>
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder={tc('搜索链路 / 设备 / 供应商 / 站点')}
              value={linkSearch}
              onChange={(e) => setLinkSearch(e.target.value)}
              style={{ width: 220 }}
            />
            <Select
              allowClear
              placeholder={tc('供应商')}
              value={supplierFilter}
              onChange={setSupplierFilter}
              options={supplierOptions}
              style={{ width: 140 }}
            />
            <Select
              allowClear
              placeholder={tc('站点路由')}
              value={siteRouteFilter}
              onChange={setSiteRouteFilter}
              options={siteRouteOptions}
              style={{ width: 180 }}
              showSearch
              optionFilterProp="label"
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => openLinkModal()}>{tc('配置骨干链路')}</Button>
            <Tooltip title={tc('从端口描述 bw(100Mbps) 同步链路合同带宽')}>
              <Button icon={<SyncOutlined />} loading={syncing} onClick={syncBandwidth}>{tc('同步端口带宽')}</Button>
            </Tooltip>
          </Space>
        }
      >
        <Alert
          type="info"
          showIcon
          className="capacity-link-hint"
          message="选用 Vlan-interface / Vlanif 子接口；端口描述标注 bw(100Mbps) 可自动写入合同带宽；利用率超链路或平台阈值触发告警"
        />
        <Table<LinkUsage>
          {...dataTableProps(TABLE_SCROLL.xl)}
          size="small"
          className="data-table capacity-data-table capacity-link-table"
          rowKey="link_id"
          loading={loading}
          dataSource={filteredLinks}
          pagination={pagination}
          scroll={{ x: 1100 }}
          locale={{ emptyText: linkSearch || supplierFilter || siteRouteFilter ? "无匹配链路" : "暂无骨干链路 · 点击「配置骨干链路」智能推荐或手动选配" }}
          columns={[
            {
              title: tc('链路'),
              dataIndex: "name",
              fixed: "left",
              width: 160,
              ellipsis: true,
              sorter: (a, b) => a.name.localeCompare(b.name),
            },
            {
              title: tc('供应商'),
              dataIndex: "supplier",
              width: 120,
              ellipsis: true,
              filters: supplierOptions.map((o) => ({ text: o.label, value: o.value })),
              onFilter: (val, r) => (r.supplier || "") === val,
              render: (v?: string | null) => v || "—",
            },
            {
              title: tc('站点路由'),
              key: "site_route",
              width: 140,
              ellipsis: true,
              filters: siteRouteOptions.map((o) => ({ text: o.label, value: o.value })),
              onFilter: (val, r) => siteRouteKey(r) === val,
              render: (_: unknown, r) => (
                <Tooltip title={[r.site_a, r.site_z].filter(Boolean).join(" → ") || undefined}>
                  <span>{siteRouteLabel(r)}</span>
                </Tooltip>
              ),
            },
            {
              title: tc('类型'),
              dataIndex: "type",
              width: 110,
              filters: Object.entries(LINK_TYPE_LABEL).map(([value, text]) => ({ text, value })),
              onFilter: (val, r) => r.type === val,
              render: (t: string) => (
                <Tag color={t === "dci" ? "blue" : "green"}>{LINK_TYPE_LABEL[t] || t}</Tag>
              ),
            },
            {
              title: tc('A 端'),
              key: "a",
              width: 220,
              render: (_: unknown, r) => (
                <Space direction="vertical" size={0}>
                  <span>{r.device_a}</span>
                  {r.interface_a ? <InterfaceNameCell name={r.interface_a} /> : null}
                  {r.interface_a_description ? (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }} title={r.interface_a_description}>
                      {r.interface_a_description.length > 48
                        ? `${r.interface_a_description.slice(0, 47)}…`
                        : r.interface_a_description}
                    </Typography.Text>
                  ) : null}
                </Space>
              ),
            },
            {
              title: tc('Z 端'),
              key: "z",
              width: 220,
              render: (_: unknown, r) => (
                <Space direction="vertical" size={0}>
                  <span>{r.device_z}</span>
                  {r.interface_z ? <InterfaceNameCell name={r.interface_z} /> : null}
                  {r.interface_z_description ? (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }} title={r.interface_z_description}>
                      {r.interface_z_description.length > 48
                        ? `${r.interface_z_description.slice(0, 47)}…`
                        : r.interface_z_description}
                    </Typography.Text>
                  ) : null}
                </Space>
              ),
            },
            {
              title: tc('合同带宽'),
              dataIndex: "capacity_mbps",
              width: 100,
              align: "right",
              sorter: (a, b) => a.capacity_mbps - b.capacity_mbps,
              render: (v: number) => fmtBw(v),
            },
            {
              title: tc('利用率'),
              dataIndex: "utilization_pct",
              width: 220,
              defaultSortOrder: "descend",
              sorter: (a, b) => a.utilization_pct - b.utilization_pct,
              render: (v: number, r) => (
                <Tooltip title={utilizationTooltip(r, v)}>
                  <Progress
                    percent={Math.round(v)}
                    size="small"
                    strokeColor={utilColor(v)}
                    format={(p) => `${p}%`}
                  />
                </Tooltip>
              ),
            },
            {
              title: tc('操作'),
              key: "op",
              width: 96,
              fixed: "right",
              className: "table-actions-col",
              render: (_: unknown, r) => (
                <Space size={0}>
                  <Tooltip title={tc('编辑端点与告警阈值')}>
                    <Button
                      type="text"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => openLinkModal(r)}
                    />
                  </Tooltip>
                  <Popconfirm title={tc('删除该骨干链路？')} onConfirm={() => deleteLink(r.link_id)} okText={tc('删除')} cancelText={tc('取消')}>
                    <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <BackboneLinkModal
        open={linkModalOpen}
        devices={devices}
        editLink={editingLink}
        onClose={closeLinkModal}
        onSaved={load}
      />
    </div>
  );
}

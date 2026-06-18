import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Input,
  Popconfirm,
  Progress,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
} from "antd";
import { DeleteOutlined, PlusOutlined, SearchOutlined, SyncOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Device, LinkUsage, SiteCapacity } from "../api/types";
import BackboneLinkModal from "../components/BackboneLinkModal";
import InterfaceNameCell from "../components/InterfaceNameCell";
import { utilColor } from "../charts/options";
import { fetchAllPages } from "../utils/pagination";

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

export default function Capacity() {
  const { message } = AntApp.useApp();
  const [sites, setSites] = useState<SiteCapacity[]>([]);
  const [links, setLinks] = useState<LinkUsage[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [siteSearch, setSiteSearch] = useState("");
  const [linkSearch, setLinkSearch] = useState("");

  // Devices are only needed by the "配置骨干链路" drawer — load lazily on open,
  // never on the 10s capacity poll (which would refetch the whole fleet).
  const [devices, setDevices] = useState<Device[]>([]);
  const [devicesLoaded, setDevicesLoaded] = useState(false);
  const [linkModalOpen, setLinkModalOpen] = useState(false);

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
      message.error("容量数据加载失败，请稍后重试");
    } finally {
      if (showSpinner) setLoading(false);
    }
  }

  async function openLinkModal() {
    setLinkModalOpen(true);
    if (!devicesLoaded) {
      try {
        const d = await fetchAllPages<Device>("/devices");
        setDevices(d);
        setDevicesLoaded(true);
      } catch {
        message.error("设备列表加载失败");
      }
    }
  }

  async function syncBandwidth() {
    setSyncing(true);
    try {
      await api.post("/capacity/links/sync-bandwidth");
      await load();
      message.success("已从端口描述同步合同带宽");
    } catch {
      message.error("同步合同带宽失败");
    } finally {
      setSyncing(false);
    }
  }

  async function deleteLink(linkId: number) {
    try {
      await api.delete(`/capacity/links/${linkId}`);
      message.success("骨干链路已删除");
      await load();
    } catch {
      message.error("删除骨干链路失败");
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
    if (!q) return links;
    return links.filter(
      (l) =>
        l.name.toLowerCase().includes(q) ||
        l.device_a.toLowerCase().includes(q) ||
        l.device_z.toLowerCase().includes(q),
    );
  }, [links, linkSearch]);

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
          <Statistic title="Fabric 总容量" value={gbps(totalCap)} suffix="Gbps" />
        </Card>
        <Card className="capacity-kpi-card">
          <Statistic
            title="已分配带宽"
            value={gbps(totalUsed)}
            suffix="Gbps"
            valueStyle={{ color: "#ff6600" }}
          />
        </Card>
        <Card className="capacity-kpi-card capacity-kpi-util">
          <div className="capacity-kpi-util-label">全域带宽分配率</div>
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
            placeholder="搜索站点名称 / 编码"
            value={siteSearch}
            onChange={(e) => setSiteSearch(e.target.value)}
            style={{ width: 240 }}
          />
        }
      >
        <Table<SiteCapacity>
          size="small"
          rowKey="site_id"
          loading={loading}
          dataSource={filteredSites}
          pagination={pagination}
          scroll={{ x: 720 }}
          locale={{ emptyText: siteSearch ? "无匹配站点" : "暂无站点容量数据" }}
          columns={[
            {
              title: "站点",
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
              title: "设备",
              dataIndex: "devices",
              width: 90,
              align: "right",
              sorter: (a, b) => a.devices - b.devices,
              render: (v: number) => `${v} 台`,
            },
            {
              title: "已分配 / 总容量",
              key: "cap",
              width: 180,
              align: "right",
              sorter: (a, b) => a.used_mbps - b.used_mbps,
              render: (_: unknown, r) => `${gbps(r.used_mbps)} / ${gbps(r.capacity_mbps)} Gbps`,
            },
            {
              title: "带宽分配率",
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
              placeholder="搜索链路 / 设备"
              value={linkSearch}
              onChange={(e) => setLinkSearch(e.target.value)}
              style={{ width: 220 }}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={openLinkModal}>
              配置骨干链路
            </Button>
            <Tooltip title="从端口描述 bw(100Mbps) 同步链路合同带宽">
              <Button icon={<SyncOutlined />} loading={syncing} onClick={syncBandwidth}>
                同步端口带宽
              </Button>
            </Tooltip>
          </Space>
        }
      >
        <Alert
          type="info"
          showIcon
          className="capacity-link-hint"
          message="选用 Vlan-interface / Vlanif 子接口；端口描述标注 bw(100Mbps) 可自动写入合同带宽，利用率超 85% 触发告警"
        />
        <Table<LinkUsage>
          size="small"
          rowKey="link_id"
          loading={loading}
          dataSource={filteredLinks}
          pagination={pagination}
          scroll={{ x: 900 }}
          locale={{ emptyText: linkSearch ? "无匹配链路" : "暂无骨干链路 · 点击「配置骨干链路」智能推荐或手动选配" }}
          columns={[
            {
              title: "链路",
              dataIndex: "name",
              fixed: "left",
              width: 180,
              ellipsis: true,
              sorter: (a, b) => a.name.localeCompare(b.name),
            },
            {
              title: "类型",
              dataIndex: "type",
              width: 110,
              filters: Object.entries(LINK_TYPE_LABEL).map(([value, text]) => ({ text, value })),
              onFilter: (val, r) => r.type === val,
              render: (t: string) => (
                <Tag color={t === "dci" ? "blue" : "green"}>{LINK_TYPE_LABEL[t] || t}</Tag>
              ),
            },
            {
              title: "A 端",
              key: "a",
              width: 200,
              render: (_: unknown, r) => (
                <Space direction="vertical" size={0}>
                  <span>{r.device_a}</span>
                  {r.interface_a ? <InterfaceNameCell name={r.interface_a} /> : null}
                </Space>
              ),
            },
            {
              title: "Z 端",
              key: "z",
              width: 200,
              render: (_: unknown, r) => (
                <Space direction="vertical" size={0}>
                  <span>{r.device_z}</span>
                  {r.interface_z ? <InterfaceNameCell name={r.interface_z} /> : null}
                </Space>
              ),
            },
            {
              title: "合同带宽",
              dataIndex: "capacity_mbps",
              width: 100,
              align: "right",
              sorter: (a, b) => a.capacity_mbps - b.capacity_mbps,
              render: (v: number) => fmtBw(v),
            },
            {
              title: "利用率",
              dataIndex: "utilization_pct",
              width: 220,
              defaultSortOrder: "descend",
              sorter: (a, b) => a.utilization_pct - b.utilization_pct,
              render: (v: number, r) => (
                <Tooltip title={`流量 ${fmtBw(r.traffic_mbps)} · 峰值 ${r.peak_utilization_pct ?? v}%`}>
                  <Progress percent={Math.round(v)} size="small" strokeColor={utilColor(v)} />
                </Tooltip>
              ),
            },
            {
              title: "操作",
              key: "op",
              width: 80,
              fixed: "right",
              render: (_: unknown, r) => (
                <Popconfirm title="删除该骨干链路？" onConfirm={() => deleteLink(r.link_id)} okText="删除" cancelText="取消">
                  <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>

      <BackboneLinkModal
        open={linkModalOpen}
        devices={devices}
        onClose={() => setLinkModalOpen(false)}
        onCreated={load}
      />
    </div>
  );
}

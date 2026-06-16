import { useEffect, useMemo, useState } from "react";
import {
  App as AntApp,
  Button,
  Card,
  Empty,
  Popconfirm,
  Progress,
  Statistic,
  Table,
  Tag,
  Tooltip,
} from "antd";
import { DeleteOutlined, PlusOutlined, SyncOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Device, LinkUsage, SiteCapacity } from "../api/types";
import BackboneLinkModal from "../components/BackboneLinkModal";
import InterfaceNameCell from "../components/InterfaceNameCell";
import EChart from "../components/EChart";
import { linkUtilBarOption, utilColor } from "../charts/options";
import { dataTableProps } from "../utils/table";
import { fetchAllPages } from "../utils/pagination";

const LINK_TYPE_LABEL: Record<string, string> = {
  dci: "跨站点 DCI",
  intra_dc: "站内互联",
  access: "接入",
  uplink: "上联",
};

function fmtBw(mbps: number) {
  return mbps >= 1000 ? `${Math.round(mbps / 1000)} Gbps` : `${mbps} Mbps`;
}

export default function Capacity() {
  const { message } = AntApp.useApp();
  const [sites, setSites] = useState<SiteCapacity[]>([]);
  const [links, setLinks] = useState<LinkUsage[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [linkModalOpen, setLinkModalOpen] = useState(false);

  async function load() {
    const [s, l, d] = await Promise.all([
      api.get<SiteCapacity[]>("/capacity/sites"),
      api.get<LinkUsage[]>("/capacity/links/usage"),
      fetchAllPages<Device>("/devices"),
    ]);
    setSites(s.data);
    setLinks(l.data);
    setDevices(d);
  }

  async function syncBandwidth() {
    setSyncing(true);
    try {
      await api.post("/capacity/links/sync-bandwidth");
      await load();
      message.success("已从端口描述同步合同带宽");
    } finally {
      setSyncing(false);
    }
  }

  async function deleteLink(linkId: number) {
    await api.delete(`/capacity/links/${linkId}`);
    message.success("骨干链路已删除");
    await load();
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const totalCap = sites.reduce((a, s) => a + s.capacity_mbps, 0);
  const totalUsed = sites.reduce((a, s) => a + s.used_mbps, 0);
  const utilPct = totalCap ? Math.round((totalUsed / totalCap) * 1000) / 10 : 0;

  const linkChart = useMemo(
    () => links.map((l) => ({ name: l.name, util: l.utilization_pct })),
    [links],
  );
  const linkOpt = useMemo(() => linkUtilBarOption(linkChart), [linkChart]);

  return (
    <div className="capacity-page">
      <div className="capacity-kpi-row">
        <Card className="capacity-kpi-card">
          <Statistic title="Fabric 总容量" value={Math.round(totalCap / 1000)} suffix="Gbps" />
        </Card>
        <Card className="capacity-kpi-card">
          <Statistic
            title="已分配带宽"
            value={Math.round(totalUsed / 1000)}
            suffix="Gbps"
            valueStyle={{ color: "#1677ff" }}
          />
        </Card>
        <Card className="capacity-kpi-card capacity-kpi-util">
          <div className="capacity-kpi-util-label">全域带宽分配率</div>
          <Progress percent={utilPct} strokeColor={utilColor(utilPct)} strokeWidth={10} />
        </Card>
      </div>

      <Card className="capacity-section-card" title="Fabric 站点容量">
        <div className="capacity-sites-grid">
          {sites.map((s) => (
            <Card type="inner" key={s.site_id} className="capacity-site-card" title={`${s.code} · ${s.site}`}>
              <div className="capacity-site-gauge">
                <Progress
                  type="dashboard"
                  percent={s.utilization_pct}
                  strokeColor={utilColor(s.utilization_pct)}
                  size={120}
                />
              </div>
              <div className="capacity-site-meta">
                {Math.round(s.used_mbps / 1000)} / {Math.round(s.capacity_mbps / 1000)} Gbps · {s.devices} 台设备
              </div>
            </Card>
          ))}
        </div>
      </Card>

      <Card
        className="capacity-section-card"
        title="骨干链路 · 利用率"
        extra={
          <Button.Group>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setLinkModalOpen(true)}>
              配置骨干链路
            </Button>
            <Tooltip title="从端口描述 bw(100Mbps) 同步链路合同带宽">
              <Button icon={<SyncOutlined />} loading={syncing} onClick={syncBandwidth}>
                同步端口带宽
              </Button>
            </Tooltip>
          </Button.Group>
        }
      >
        <div className="capacity-link-hint">
          骨干链路请选用 VLAN 子接口（Vlan-interface / Vlanif）；端口描述标注 <Tag>bw(100Mbps)</Tag> 或 <Tag>bw(10Gbps)</Tag> 可自动写入合同带宽 · 利用率超 85% 触发告警
        </div>
        {linkChart.length > 0 && (
          <div className="capacity-link-chart">
            <EChart option={linkOpt} height={Math.max(240, linkChart.length * 36)} />
          </div>
        )}
        <Table
          rowKey="link_id"
          className="capacity-link-table"
          style={{ width: "100%" }}
          dataSource={links}
          pagination={false}
          scroll={{ x: 1280 }}
          locale={{ emptyText: <Empty description="暂无链路 · 点击「配置骨干链路」智能推荐或手动选配" /> }}
          {...dataTableProps(undefined, false)}
          columns={[
            { title: "链路", dataIndex: "name", width: 140, ellipsis: true },
            {
              title: "类型",
              dataIndex: "type",
              width: 108,
              render: (t) => <Tag>{LINK_TYPE_LABEL[t] || t}</Tag>,
            },
            {
              title: "A 端设备",
              dataIndex: "device_a",
              width: 180,
              ellipsis: { showTitle: false },
              render: (v: string) => (
                <Tooltip title={v}>
                  <span className="capacity-device-name">{v}</span>
                </Tooltip>
              ),
            },
            {
              title: "A 端口",
              dataIndex: "interface_a",
              width: 148,
              render: (v?: string) => (v ? <InterfaceNameCell name={v} /> : "—"),
            },
            {
              title: "Z 端设备",
              dataIndex: "device_z",
              width: 180,
              ellipsis: { showTitle: false },
              render: (v: string) => (
                <Tooltip title={v}>
                  <span className="capacity-device-name">{v}</span>
                </Tooltip>
              ),
            },
            {
              title: "Z 端口",
              dataIndex: "interface_z",
              width: 148,
              render: (v?: string) => (v ? <InterfaceNameCell name={v} /> : "—"),
            },
            {
              title: "合同带宽",
              dataIndex: "capacity_mbps",
              width: 100,
              render: (v) => fmtBw(v),
            },
            {
              title: "实时流量",
              dataIndex: "traffic_mbps",
              width: 100,
              render: (v) => (v != null ? fmtBw(v) : "—"),
            },
            {
              title: "峰值利用率",
              dataIndex: "utilization_pct",
              width: 148,
              render: (v) => (
                <Progress percent={v} size="small" strokeColor={utilColor(v)} style={{ minWidth: 96, maxWidth: 132 }} />
              ),
            },
            {
              title: "",
              width: 48,
              fixed: "right",
              render: (_, row) => (
                <Popconfirm title="删除此骨干链路？" onConfirm={() => deleteLink(row.link_id)}>
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} />
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

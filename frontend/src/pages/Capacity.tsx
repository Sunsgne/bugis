import { useEffect, useState } from "react";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Progress,
  Space,
  Statistic,
  Tooltip,
} from "antd";
import { PlusOutlined, SyncOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Device, LinkUsage, SiteCapacity } from "../api/types";
import BackboneLinkModal from "../components/BackboneLinkModal";
import BackboneLinkCards from "../components/BackboneLinkCards";
import { utilColor } from "../charts/options";
import { fetchAllPages } from "../utils/pagination";

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
        className="capacity-section-card capacity-backbone-card"
        title="骨干链路 · 利用率"
        extra={
          <Space wrap>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setLinkModalOpen(true)}>
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
        <BackboneLinkCards links={links} onDelete={deleteLink} />
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

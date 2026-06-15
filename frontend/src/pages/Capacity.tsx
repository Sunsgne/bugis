import { useEffect, useMemo, useState } from "react";
import { Button, Card, Empty, Progress, Statistic, Table, Tag, Tooltip } from "antd";
import { SyncOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { LinkUsage, SiteCapacity } from "../api/types";
import EChart from "../components/EChart";
import { linkUtilBarOption, utilColor } from "../charts/options";
import { dataTableProps } from "../utils/table";

function fmtBw(mbps: number) {
  return mbps >= 1000 ? `${Math.round(mbps / 1000)} Gbps` : `${mbps} Mbps`;
}

export default function Capacity() {
  const [sites, setSites] = useState<SiteCapacity[]>([]);
  const [links, setLinks] = useState<LinkUsage[]>([]);
  const [syncing, setSyncing] = useState(false);

  async function load() {
    const [s, l] = await Promise.all([
      api.get<SiteCapacity[]>("/capacity/sites"),
      api.get<LinkUsage[]>("/capacity/links/usage"),
    ]);
    setSites(s.data);
    setLinks(l.data);
  }

  async function syncBandwidth() {
    setSyncing(true);
    try {
      await api.post("/capacity/links/sync-bandwidth");
      await load();
    } finally {
      setSyncing(false);
    }
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
          <Tooltip title="从端口描述 bw(100Mbps) 同步链路合同带宽">
            <Button icon={<SyncOutlined />} loading={syncing} onClick={syncBandwidth}>
              同步端口带宽
            </Button>
          </Tooltip>
        }
      >
        <div className="capacity-link-hint">
          端口描述标注 <Tag>bw(100Mbps)</Tag> 或 <Tag>bw(10Gbps)</Tag> · SNMP 发现后自动写入容量 · 利用率超 85% 触发告警
        </div>
        {linkChart.length > 0 && (
          <div className="capacity-link-chart">
            <EChart option={linkOpt} height={Math.max(240, linkChart.length * 36)} />
          </div>
        )}
        <Table
          rowKey="link_id"
          style={{ width: "100%" }}
          dataSource={links}
          pagination={false}
          locale={{ emptyText: <Empty description="暂无链路 · 添加 DCI/Fabric 链路或同步端口带宽" /> }}
          {...dataTableProps(undefined, false)}
          columns={[
            { title: "链路", dataIndex: "name", width: "18%", ellipsis: true },
            { title: "类型", dataIndex: "type", width: "8%", render: (t) => <Tag>{t}</Tag> },
            { title: "A 端", dataIndex: "device_a", width: "16%", ellipsis: true },
            { title: "Z 端", dataIndex: "device_z", width: "16%", ellipsis: true },
            {
              title: "合同带宽",
              dataIndex: "capacity_mbps",
              width: "12%",
              render: (v) => fmtBw(v),
            },
            {
              title: "实时流量",
              dataIndex: "traffic_mbps",
              width: "12%",
              render: (v) => (v != null ? fmtBw(v) : "-"),
            },
            {
              title: "峰值利用率",
              dataIndex: "utilization_pct",
              width: "10%",
              render: (v) => (
                <Progress percent={v} size="small" strokeColor={utilColor(v)} style={{ minWidth: 80, maxWidth: 140 }} />
              ),
            },
            {
              title: "已预留",
              dataIndex: "reserved_mbps",
              width: "8%",
              render: (v) => fmtBw(v),
            },
          ]}
        />
      </Card>
    </div>
  );
}

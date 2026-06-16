import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Input, Select, Space, Table, Tag, Typography } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import PageCard from "../components/PageCard";

const STATUS: Record<string, { label: string; color: string }> = {
  active: { label: "运行中", color: "green" },
  degraded: { label: "降级", color: "orange" },
  provisioning: { label: "开通中", color: "processing" },
  pending: { label: "待开通", color: "gold" },
  draft: { label: "草稿", color: "default" },
  suspended: { label: "暂停", color: "volcano" },
  failed: { label: "失败", color: "red" },
  decommissioned: { label: "已拆除", color: "default" },
};

const SERVICE: Record<string, string> = {
  l2vpn_evpn: "二层 EVPN",
  l3vpn_evpn: "三层 EVPN",
  remote_ipt: "Remote IPT",
  evpn_vpws: "EVPN VPWS",
  dci: "DCI 互联",
};

interface Row {
  id: number;
  code: string;
  name: string;
  status: string;
  bandwidth_mbps: number;
  service_type: string;
  vni?: number;
  sla_target?: string;
  endpoint_count: number;
}

export default function PortalCircuits() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string | undefined>();

  async function load() {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (q.trim()) params.q = q.trim();
      if (status) params.status = status;
      const { data } = await api.get<Row[]>("/portal/circuits", { params });
      setRows(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [status]);

  return (
    <PageCard title="我的专线" description="仅展示贵司租户下的专线资源">
      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          allowClear
          placeholder="搜索编码 / 名称"
          prefix={<SearchOutlined />}
          style={{ width: 260 }}
          onSearch={load}
          onChange={(e) => setQ(e.target.value)}
        />
        <Select
          allowClear
          placeholder="状态筛选"
          style={{ width: 140 }}
          value={status}
          onChange={setStatus}
          options={Object.entries(STATUS).map(([k, v]) => ({ value: k, label: v.label }))}
        />
        <Typography.Text type="secondary">共 {rows.length} 条</Typography.Text>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
        columns={[
          {
            title: "编码",
            dataIndex: "code",
            width: 120,
            render: (code: string, row) => (
              <Link to={`/portal/circuits/${row.id}`}>
                <Typography.Text code>{code}</Typography.Text>
              </Link>
            ),
          },
          { title: "名称", dataIndex: "name", ellipsis: true },
          {
            title: "业务类型",
            dataIndex: "service_type",
            width: 120,
            render: (t: string) => SERVICE[t] || t,
          },
          {
            title: "签约带宽",
            dataIndex: "bandwidth_mbps",
            width: 110,
            render: (v: number) => <Tag color="blue">{v} Mbps</Tag>,
          },
          { title: "VNI", dataIndex: "vni", width: 80, render: (v?: number) => v ?? "—" },
          {
            title: "SLA",
            dataIndex: "sla_target",
            width: 80,
            render: (v?: string) => v || "—",
          },
          {
            title: "端点",
            dataIndex: "endpoint_count",
            width: 64,
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 96,
            render: (st: string) => {
              const m = STATUS[st] || { label: st, color: "default" };
              return <Tag color={m.color}>{m.label}</Tag>;
            },
          },
          {
            title: "操作",
            width: 120,
            render: (_: unknown, row) => (
              <Space>
                <Link to={`/portal/circuits/${row.id}`}>详情</Link>
                <Link to={`/portal/traffic?circuit=${row.id}`}>流量</Link>
              </Space>
            ),
          },
        ]}
      />
    </PageCard>
  );
}

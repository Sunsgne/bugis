import { useEffect, useState } from "react";
import { Button, Card, Segmented, Space, Table, Tag, App as AntApp } from "antd";
import { ReloadOutlined, ThunderboltOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import type { Alarm } from "../api/types";
import { action, empty, page } from "../constants/uiCopy";

const SEV_COLOR: Record<string, string> = {
  critical: "red",
  major: "volcano",
  minor: "orange",
  warning: "gold",
  info: "blue",
};
const STATUS_COLOR: Record<string, string> = {
  active: "red",
  acknowledged: "orange",
  cleared: "green",
};

export default function Alarms() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Alarm[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string>("active");

  async function load() {
    setLoading(true);
    try {
      const q = filter === "all" ? "" : `?status=${filter}`;
      const { data } = await api.get<Alarm[]>(`/alarms${q}`);
      setRows(data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [filter]);

  async function evaluate() {
    const { data } = await api.post("/alarms/evaluate");
    message.success(`评估完成 · ${data.evaluated} 条专线 · 活跃告警 ${data.active_alarms}`);
    load();
  }
  async function ack(id: number) {
    await api.post(`/alarms/${id}/ack`, {});
    load();
  }
  async function clear(id: number) {
    await api.post(`/alarms/${id}/clear`);
    load();
  }

  return (
    <Card
      title={page.alarms}
      extra={
        <Space>
          <Segmented
            value={filter}
            onChange={(v) => setFilter(v as string)}
            options={[
              { label: "活跃", value: "active" },
              { label: "已确认", value: "acknowledged" },
              { label: "已清除", value: "cleared" },
              { label: "全域", value: "all" },
            ]}
          />
          <Button icon={<ThunderboltOutlined />} type="primary" onClick={evaluate}>
            触发评估
          </Button>
          <Button icon={<ReloadOutlined />} onClick={load} />
        </Space>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        locale={{ emptyText: filter === "active" ? empty.alarms : empty.default }}
        columns={[
          {
            title: "级别",
            dataIndex: "severity",
            width: 90,
            render: (s) => <Tag color={SEV_COLOR[s]}>{s.toUpperCase()}</Tag>,
          },
          { title: "类型", dataIndex: "kind", width: 130, render: (k) => <Tag>{k}</Tag> },
          { title: "标题", dataIndex: "title" },
          { title: "详情", dataIndex: "detail" },
          {
            title: "时间",
            dataIndex: "created_at",
            width: 170,
            render: (t) => (t ? dayjs(t).format("MM-DD HH:mm:ss") : "-"),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "操作",
            width: 150,
            render: (_, r) =>
              r.status !== "cleared" && (
                <Space>
                  {r.status === "active" && <a onClick={() => ack(r.id)}>{action.confirm}</a>}
                  <a style={{ color: "#52c41a" }} onClick={() => clear(r.id)}>
                    清除
                  </a>
                </Space>
              ),
          },
        ]}
      />
    </Card>
  );
}

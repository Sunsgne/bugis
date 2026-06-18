import { useEffect, useState } from "react";
import { Button, Empty, Segmented, Space, Table, Tag, App as AntApp } from "antd";
import { ReloadOutlined, ThunderboltOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import type { Alarm } from "../api/types";
import PageCard from "../components/PageCard";
import { dataTableProps, TABLE_SCROLL, withMobileHide } from "../utils/table";
import { action, empty, page } from "../constants/uiCopy";
import { ALARM_KIND, ALARM_SEVERITY, ALARM_STATUS, statusMeta } from "../constants/statusLabels";
import { useTc } from "@/i18n/useTc";

export default function Alarms() {
  const { tc } = useTc();
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
    <div className="alarms-page">
      <PageCard
        className="alarms-page-card"
        title={page.alarms}
        extra={
          <Space wrap className="alarms-toolbar">
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
            <Button icon={<ThunderboltOutlined />} type="primary" onClick={evaluate}>{tc('触发评估')}</Button>
            <Button icon={<ReloadOutlined />} onClick={load} />
          </Space>
        }
      >
        <Table
          rowKey="id"
          loading={loading}
          dataSource={rows}
          style={{ width: "100%" }}
          {...dataTableProps(TABLE_SCROLL.md)}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={filter === "active" ? empty.alarms : empty.default}
              />
            ),
          }}
          columns={withMobileHide(
            [
            {
              title: tc('级别'),
              dataIndex: "severity",
              width: "10%",
              render: (s) => {
                const m = statusMeta(ALARM_SEVERITY, s);
                return <Tag color={m.color}>{m.label}</Tag>;
              },
            },
            {
              title: tc('类型'),
              dataIndex: "kind",
              width: "10%",
              ellipsis: true,
              render: (k) => <Tag>{ALARM_KIND[k] || k}</Tag>,
            },
            { title: "标题", dataIndex: "title", width: "26%", ellipsis: true },
            { title: "详情", dataIndex: "detail", width: "24%", ellipsis: true, render: (v) => v || "—" },
            {
              title: tc('时间'),
              dataIndex: "created_at",
              width: "14%",
              render: (t) => (t ? dayjs(t).format("MM-DD HH:mm:ss") : "—"),
            },
            {
              title: tc('状态'),
              dataIndex: "status",
              width: "10%",
              render: (s, r) => {
                const m = statusMeta(ALARM_STATUS, s);
                const auto = r.acknowledged_by === "system:auto-notify";
                return (
                  <Tag color={m.color}>
                    {auto && s === "acknowledged" ? "已确认(自动)" : m.label}
                  </Tag>
                );
              },
            },
            {
              title: tc('操作'),
              width: "12%",
              className: "table-actions",
              render: (_, r) =>
                r.status !== "cleared" ? (
                  <Space size={4}>
                    {r.status === "active" && (
                      <Button type="link" size="small" onClick={() => ack(r.id)}>
                        {action.ack}
                      </Button>
                    )}
                    <Button type="link" size="small" onClick={() => clear(r.id)}>{tc('清除')}</Button>
                  </Space>
                ) : null,
            },
          ],
            ["kind", "detail", "status"],
          )}
        />
      </PageCard>
    </div>
  );
}

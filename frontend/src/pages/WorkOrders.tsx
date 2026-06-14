import { useEffect, useState } from "react";
import { Card, Table, Tag, Drawer, Timeline, Collapse, Empty } from "antd";
import { api } from "../api/client";
import type { WorkOrder } from "../api/types";

const STATUS_COLOR: Record<string, string> = {
  draft: "default",
  submitted: "gold",
  approved: "blue",
  rejected: "red",
  scheduled: "cyan",
  running: "processing",
  completed: "green",
  failed: "red",
  rolled_back: "orange",
  cancelled: "default",
};
const TYPE_LABEL: Record<string, string> = {
  provision: "开通",
  modify: "变更",
  decommission: "拆除",
  migrate: "迁移",
};
const LEVEL_COLOR: Record<string, string> = {
  info: "blue",
  warning: "orange",
  error: "red",
};

export default function WorkOrders() {
  const [rows, setRows] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState<WorkOrder | null>(null);

  async function load() {
    setLoading(true);
    try {
      const { data } = await api.get<WorkOrder[]>("/work-orders");
      setRows(data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  async function openDetail(id: number) {
    const { data } = await api.get<WorkOrder>(`/work-orders/${id}`);
    setCurrent(data);
  }

  return (
    <Card title="工单流转">
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        onRow={(r) => ({ onClick: () => openDetail(r.id), style: { cursor: "pointer" } })}
        columns={[
          { title: "工单号", dataIndex: "code" },
          { title: "标题", dataIndex: "title" },
          {
            title: "类型",
            dataIndex: "type",
            render: (t) => <Tag>{TYPE_LABEL[t] || t}</Tag>,
          },
          {
            title: "状态",
            dataIndex: "status",
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          { title: "申请人", dataIndex: "requested_by" },
          { title: "审批人", dataIndex: "approved_by" },
          {
            title: "配置作业",
            render: (_, r) => <Tag color="geekblue">{r.config_jobs.length}</Tag>,
          },
        ]}
      />

      <Drawer
        title={current ? `工单 ${current.code}` : ""}
        width={720}
        open={!!current}
        onClose={() => setCurrent(null)}
      >
        {current && (
          <>
            <div style={{ marginBottom: 16 }}>
              <Tag color={STATUS_COLOR[current.status]}>{current.status}</Tag>
              <Tag>{TYPE_LABEL[current.type]}</Tag>
            </div>

            <h4>处理过程</h4>
            <Timeline
              items={current.events.map((e) => ({
                color: LEVEL_COLOR[e.level] || "blue",
                children: (
                  <span>
                    {e.message}
                    {e.actor && <Tag style={{ marginLeft: 8 }}>{e.actor}</Tag>}
                  </span>
                ),
              }))}
            />

            <h4>配置作业 (rendered config)</h4>
            {current.config_jobs.length ? (
              <Collapse
                items={current.config_jobs.map((j) => ({
                  key: j.id,
                  label: (
                    <span>
                      设备 #{j.device_id} · {j.operation} ·{" "}
                      <Tag color={j.status.includes("fail") ? "red" : "green"}>{j.status}</Tag>
                      <Tag>{j.transport}</Tag>
                    </span>
                  ),
                  children: (
                    <pre className="config-pre">{j.rendered_config || "(空)"}</pre>
                  ),
                }))}
              />
            ) : (
              <Empty />
            )}
          </>
        )}
      </Drawer>
    </Card>
  );
}

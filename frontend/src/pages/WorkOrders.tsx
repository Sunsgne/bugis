import { useEffect, useState } from "react";
import {
  Card, Table, Tag, Drawer, Timeline, Collapse, Empty, Space, Button, Modal,
  Form, Input, Popconfirm, App as AntApp,
} from "antd";
import { EditOutlined, DeleteOutlined, StopOutlined } from "@ant-design/icons";
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
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState<WorkOrder | null>(null);
  const [editTarget, setEditTarget] = useState<WorkOrder | null>(null);
  const [editForm] = Form.useForm();

  async function doEdit() {
    const v = await editForm.validateFields();
    await api.patch(`/work-orders/${editTarget!.id}`, v);
    message.success("工单已更新");
    setEditTarget(null);
    load();
  }
  async function cancelWo(id: number) {
    try {
      await api.post(`/work-orders/${id}/cancel`);
      message.success("已取消");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "取消失败");
    }
  }
  async function deleteWo(id: number) {
    try {
      await api.delete(`/work-orders/${id}`);
      message.success("已删除");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "删除失败");
    }
  }

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
          {
            title: "操作",
            width: 170,
            render: (_, r) => (
              <Space onClick={(e) => e.stopPropagation()}>
                <a onClick={() => { setEditTarget(r); editForm.setFieldsValue({ title: r.title, notes: r.notes }); }}>
                  <EditOutlined /> 编辑
                </a>
                {!["running", "completed"].includes(r.status) && (
                  <Popconfirm title="取消该工单?" onConfirm={() => cancelWo(r.id)}>
                    <a style={{ color: "#fa8c16" }}><StopOutlined /></a>
                  </Popconfirm>
                )}
                <Popconfirm title="删除该工单?" onConfirm={() => deleteWo(r.id)}>
                  <a style={{ color: "#cf1322" }}><DeleteOutlined /></a>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal title="编辑工单" open={!!editTarget} onOk={doEdit} onCancel={() => setEditTarget(null)}>
        <Form form={editForm} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

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

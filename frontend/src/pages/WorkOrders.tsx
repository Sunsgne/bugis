import { useEffect, useState } from "react";
import {
  Button,
  Card, Table, Tag, Drawer, Timeline, Collapse, Empty, Space, Modal,
  Form, Input, Popconfirm, App as AntApp,
} from "antd";
import { EditOutlined, DeleteOutlined, StopOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { WorkOrder } from "../api/types";
import PageCard from "../components/PageCard";
import { dataTableProps } from "../utils/table";
import { action, empty, page, toast } from "../constants/uiCopy";

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
    message.success(toast.saved);
    setEditTarget(null);
    load();
  }
  async function cancelWo(id: number) {
    try {
      await api.post(`/work-orders/${id}/cancel`);
      message.success("工单已撤销");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }
  async function deleteWo(id: number) {
    try {
      await api.delete(`/work-orders/${id}`);
      message.success(toast.deleted);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
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
    <PageCard title={page.workOrders}>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        {...dataTableProps()}
        onRow={(r) => ({ onClick: () => openDetail(r.id), style: { cursor: "pointer" } })}
        columns={[
          { title: "工单号", dataIndex: "code", width: "12%", ellipsis: true },
          { title: "标题", dataIndex: "title", width: "22%", ellipsis: true },
          {
            title: "类型",
            dataIndex: "type",
            width: "8%",
            render: (t) => <Tag>{TYPE_LABEL[t] || t}</Tag>,
          },
          {
            title: "状态",
            dataIndex: "status",
            width: "10%",
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          { title: "申请人", dataIndex: "requested_by", width: "10%", ellipsis: true, render: (v) => v || "—" },
          { title: "审批人", dataIndex: "approved_by", width: "10%", ellipsis: true, render: (v) => v || "—" },
          {
            title: "配置作业",
            width: "8%",
            align: "center",
            render: (_, r) => <Tag color="geekblue">{r.config_jobs.length}</Tag>,
          },
          {
            title: "操作",
            width: "20%",
            className: "table-actions",
            render: (_, r) => (
              <Space size={4} onClick={(e) => e.stopPropagation()}>
                <Button
                  type="link"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => {
                    setEditTarget(r);
                    editForm.setFieldsValue({ title: r.title, notes: r.notes });
                  }}
                >
                  编辑
                </Button>
                {!["running", "completed"].includes(r.status) && (
                  <Popconfirm title="撤销该工单？" onConfirm={() => cancelWo(r.id)}>
                    <Button type="link" size="small" icon={<StopOutlined />} />
                  </Popconfirm>
                )}
                <Popconfirm title={`${action.confirm}${action.delete}该工单？`} onConfirm={() => deleteWo(r.id)}>
                  <Button type="link" size="small" danger icon={<DeleteOutlined />} />
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

            <h4>流转轨迹</h4>
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

            <h4>配置作业 · Rendered Config</h4>
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
              <Empty description={empty.default} />
            )}
          </>
        )}
      </Drawer>
    </PageCard>
  );
}

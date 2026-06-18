import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card, Table, Tag, Drawer, Timeline, Collapse, Empty, Space, Modal,
  Form, Input, Popconfirm, App as AntApp,
  DatePicker, Select, Typography,
} from "antd";
import {
  EditOutlined, DeleteOutlined, StopOutlined, SearchOutlined, ReloadOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import dayjs, { type Dayjs } from "dayjs";
import { api } from "../api/client";
import type { WorkOrder } from "../api/types";
import PageCard from "../components/PageCard";
import { dataTableProps } from "../utils/table";
import { formModalProps } from "../utils/formModal";
import { action, empty, page, toast } from "../constants/uiCopy";
import { WORK_ORDER_STATUS, statusMeta } from "../constants/statusLabels";
import { useTc } from "@/i18n/useTc";
import { formatUserLong, useUserDatetime, userDayjs } from "@/utils/datetime";

const { RangePicker } = DatePicker;

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

const TERMINAL = ["completed", "failed", "cancelled", "rolled_back"];

export default function WorkOrders() {
  const { tc } = useTc();
  const { timezone, datePresets, formatLong } = useUserDatetime();
  const rangePresets = useMemo(() => datePresets(), [datePresets, timezone]);
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState<WorkOrder | null>(null);
  const [editTarget, setEditTarget] = useState<WorkOrder | null>(null);
  const [editForm] = Form.useForm();

  // --- 操作日志搜索 / 过滤 ---
  const [keyword, setKeyword] = useState("");
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [typeFilter, setTypeFilter] = useState<string | undefined>();

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    const from = range?.[0]?.startOf("day");
    const to = range?.[1]?.endOf("day");
    return rows.filter((r) => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (typeFilter && r.type !== typeFilter) return false;
      if (from && to) {
        if (!r.created_at) return false;
        const ts = userDayjs(r.created_at, timezone);
        if (ts.isBefore(from) || ts.isAfter(to)) return false;
      }
      if (kw) {
        const hay = [r.code, r.title, r.requested_by, r.approved_by]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(kw)) return false;
      }
      return true;
    });
  }, [rows, keyword, range, statusFilter, typeFilter]);

  const hasFilter = !!(keyword || range || statusFilter || typeFilter);
  function resetFilters() {
    setKeyword("");
    setRange(null);
    setStatusFilter(undefined);
    setTypeFilter(undefined);
  }

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
      message.success(tc('工单已撤销'));
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
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  async function openDetail(id: number) {
    const { data } = await api.get<WorkOrder>(`/work-orders/${id}`);
    setCurrent(data);
  }

  // Live-poll the open detail drawer while the work order is still in progress,
  // so 开通/拆除 progress streams in instead of appearing only when finished.
  useEffect(() => {
    if (!current || TERMINAL.includes(current.status)) return;
    const id = current.id;
    const t = setInterval(async () => {
      try {
        const { data } = await api.get<WorkOrder>(`/work-orders/${id}`);
        setCurrent(data);
      } catch {
        /* keep last */
      }
    }, 2500);
    return () => clearInterval(t);
  }, [current?.id, current?.status]);

  return (
    <PageCard title={page.workOrders}>
      <div
        style={{
          marginBottom: 16,
          padding: "12px 16px",
          background: "var(--ant-color-fill-quaternary, #fafafa)",
          borderRadius: 10,
          border: "1px solid var(--ant-color-border-secondary, #f0f0f0)",
        }}
      >
        <Space size={[12, 12]} wrap align="center">
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder={tc('搜索工单号 / 标题 / 申请人')}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 240 }}
          />
          <RangePicker
            value={range as never}
            onChange={(v) => setRange((v as [Dayjs, Dayjs] | null) ?? null)}
            presets={rangePresets}
            allowClear
            placeholder={["开始日期", "结束日期"]}
          />
          <Select
            allowClear
            placeholder={tc('状态')}
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 130 }}
            options={Object.entries(WORK_ORDER_STATUS).map(([value, m]) => ({
              value,
              label: m.label,
            }))}
          />
          <Select
            allowClear
            placeholder={tc('类型')}
            value={typeFilter}
            onChange={setTypeFilter}
            style={{ width: 120 }}
            options={Object.entries(TYPE_LABEL).map(([value, label]) => ({
              value,
              label,
            }))}
          />
          {hasFilter && (
            <Button icon={<ReloadOutlined />} onClick={resetFilters}>{tc('重置')}</Button>
          )}
          <Typography.Text type="secondary">
            {hasFilter ? `筛选出 ${filtered.length} / ${rows.length} 条` : `共 ${rows.length} 条`}
          </Typography.Text>
        </Space>
      </div>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={filtered}
        {...dataTableProps()}
        locale={{ emptyText: hasFilter ? "无匹配工单 · 调整筛选条件" : empty.default }}
        pagination={{
          pageSize: 15,
          hideOnSinglePage: true,
          showSizeChanger: false,
          showTotal: (t) => `共 ${t} 张工单`,
        }}
        onRow={(r) => ({ onClick: () => openDetail(r.id), style: { cursor: "pointer" } })}
        columns={[
          { title: "工单号", dataIndex: "code", width: "12%", ellipsis: true },
          { title: "标题", dataIndex: "title", width: "22%", ellipsis: true },
          {
            title: tc('类型'),
            dataIndex: "type",
            width: "8%",
            render: (t) => <Tag>{TYPE_LABEL[t] || t}</Tag>,
          },
          {
            title: tc('状态'),
            dataIndex: "status",
            width: "10%",
            render: (s) => {
              const m = statusMeta(WORK_ORDER_STATUS, s);
              const busy = s === "running" || s === "scheduled";
              return (
                <Tag color={m.color} icon={busy ? <LoadingOutlined spin /> : undefined}>
                  {m.label}
                </Tag>
              );
            },
          },
          { title: "申请人", dataIndex: "requested_by", width: "10%", ellipsis: true, render: (v) => v || "—" },
          { title: "审批人", dataIndex: "approved_by", width: "10%", ellipsis: true, render: (v) => v || "—" },
          {
            title: tc('配置作业'),
            width: "8%",
            align: "center",
            render: (_, r) => <Tag color="geekblue">{r.config_jobs.length}</Tag>,
          },
          {
            title: tc('操作'),
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
                >{tc('编辑')}</Button>
                {!["running", "completed"].includes(r.status) && (
                  <Popconfirm title={tc('撤销该工单？')} onConfirm={() => cancelWo(r.id)}>
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

      <Modal
        title={tc('编辑工单')}
        open={!!editTarget}
        onOk={doEdit}
        onCancel={() => setEditTarget(null)}
        okText={action.save}
        {...formModalProps}
      >
        <Form form={editForm} layout="vertical" className="app-form">
          <Form.Item name="title" label={tc('标题')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="notes" label={tc('备注')}>
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
              <Tag color={statusMeta(WORK_ORDER_STATUS, current.status).color}>
                {statusMeta(WORK_ORDER_STATUS, current.status).label}
              </Tag>
              <Tag>{TYPE_LABEL[current.type]}</Tag>
            </div>

            <h4>{tc('流转轨迹')}</h4>
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

            <h4>{tc('配置作业 · Rendered Config')}</h4>
            {current.config_jobs.length ? (
              <Collapse
                items={current.config_jobs.map((j) => ({
                  key: j.id,
                  label: (
                    <span>
                      {j.device_name || `设备 #${j.device_id}`} · {j.operation} ·{" "}
                      <Tag color={j.status.includes("fail") ? "red" : "green"}>{j.status}</Tag>
                      <Tag>{j.transport}</Tag>
                      <Tag color="default">{formatLong(j.created_at)}</Tag>
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

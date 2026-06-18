import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  App as AntApp,
  Popconfirm,
} from "antd";
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Paginated, Tenant } from "../api/types";
import TenantPortalUsersModal from "../components/TenantPortalUsersModal";
import ListToolbar from "../components/ListToolbar";
import PageCard from "../components/PageCard";
import { dataTableProps, PAGE_SIZE_OPTIONS, pageRangeLabel, TABLE_SCROLL, tablePagination, withMobileHide } from "../utils/table";
import { formModalProps } from "../utils/formModal";
import { TENANT_STATUS, statusMeta } from "../constants/statusLabels";
import { page as pageCopy } from "../constants/uiCopy";
import { useTc } from "@/i18n/useTc";

const TYPE_LABEL: Record<string, string> = {
  enterprise: "企业专线",
  hybrid_cloud: "混合云接入",
  public_cloud: "公有云接入",
  internal: "内部业务",
};

export default function Tenants() {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Tenant[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [portalTenant, setPortalTenant] = useState<Tenant | null>(null);
  const [form] = Form.useForm();

  async function load(p = page, ps = pageSize, q = search) {
    setLoading(true);
    try {
      const qs = new URLSearchParams({ page: String(p), page_size: String(ps) });
      if (q.trim()) qs.set("q", q.trim());
      const { data } = await api.get<Paginated<Tenant>>(`/tenants?${qs}`);
      setRows(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, pageSize]);

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post("/tenants", values);
      message.success(tc('客户已创建'));
      setOpen(false);
      form.resetFields();
      load(1);
      setPage(1);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function remove(id: number) {
    try {
      await api.delete(`/tenants/${id}`);
      message.success(tc('已删除'));
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "删除失败");
    }
  }

  return (
    <PageCard
      title={pageCopy.tenants}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>{tc('新建客户')}</Button>
      }
    >
      <ListToolbar
        summary={pageRangeLabel(total, page, pageSize)}
        left={
          <Input.Search
            allowClear
            placeholder={tc('搜索客户名称或编码')}
            style={{ width: 280 }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onSearch={() => {
              setPage(1);
              load(1, pageSize, search);
            }}
            enterButton={<SearchOutlined />}
          />
        }
        right={
          <Select
            value={pageSize}
            style={{ width: 96 }}
            options={PAGE_SIZE_OPTIONS.map((n) => ({ value: n, label: `${n} 条/页` }))}
            onChange={(ps) => {
              setPage(1);
              setPageSize(ps);
            }}
          />
        }
      />

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        {...dataTableProps(TABLE_SCROLL.md)}
        pagination={tablePagination(total, page, pageSize, (p, ps) => {
          setPage(p);
          setPageSize(ps);
        })}
        columns={withMobileHide(
          [
          { title: "名称", dataIndex: "name", width: "16%", ellipsis: true },
          {
            title: tc('编码'),
            dataIndex: "code",
            width: "10%",
            render: (c) => <Tag>{c}</Tag>,
          },
          {
            title: tc('类型'),
            dataIndex: "type",
            width: "12%",
            ellipsis: true,
            render: (t) => TYPE_LABEL[t] || t,
          },
          {
            title: tc('状态'),
            dataIndex: "status",
            width: "8%",
            render: (s) => {
              const m = statusMeta(TENANT_STATUS, s);
              return <Tag color={m.color}>{m.label}</Tag>;
            },
          },
          {
            title: tc('专线数'),
            dataIndex: "circuits_total",
            width: "8%",
            align: "right",
            render: (n) => n ?? 0,
          },
          {
            title: tc('联系人'),
            dataIndex: "contact_name",
            width: "12%",
            ellipsis: true,
            render: (v) => v || "—",
          },
          {
            title: tc('邮箱'),
            dataIndex: "contact_email",
            width: "18%",
            ellipsis: true,
            render: (v) => v || "—",
          },
          {
            title: tc('操作'),
            width: "16%",
            className: "table-actions",
            render: (_, r) => (
              <Space size={4} className="table-actions">
                <Link to={`/circuits?tenant=${r.id}`}>{tc('查看专线')}</Link>
                <Button type="link" size="small" onClick={() => setPortalTenant(r)}>{tc('门户账号')}</Button>
                <Popconfirm title={tc('确认删除?')} onConfirm={() => remove(r.id)}>
                  <Button type="link" size="small" danger>{tc('删除')}</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ],
          ["code", "type", "circuits_total", "contact_name", "contact_email"],
        )}
      />

      <Modal
        title={tc('新建客户')}
        open={open}
        onOk={onCreate}
        onCancel={() => setOpen(false)}
        okText={tc('创建')}
        {...formModalProps}
      >
        <Form form={form} layout="vertical" className="app-form" initialValues={{ type: "enterprise", status: "active" }}>
          <Form.Item name="name" label={tc('客户名称')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label={tc('编码')} rules={[{ required: true }]}>
            <Input placeholder={tc('例如 BANK-BJ')} />
          </Form.Item>
          <Form.Item name="type" label={tc('类型')}>
            <Select options={Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))} />
          </Form.Item>
          <Form.Item name="contact_name" label={tc('联系人')}>
            <Input />
          </Form.Item>
          <Form.Item name="contact_email" label={tc('邮箱')}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <TenantPortalUsersModal
        tenantId={portalTenant?.id ?? 0}
        tenantName={portalTenant?.name ?? ""}
        open={!!portalTenant}
        onClose={() => setPortalTenant(null)}
      />
    </PageCard>
  );
}

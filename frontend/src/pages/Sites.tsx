import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Table,
  Tag,
  App as AntApp,
  Popconfirm,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Select } from "antd";
import { api } from "../api/client";
import type { Controller, Site } from "../api/types";
import PageCard from "../components/PageCard";
import { dataTableProps } from "../utils/table";
import { formModalProps } from "../utils/formModal";
import { action, page, toast } from "../constants/uiCopy";
import { useTc } from "@/i18n/useTc";
import { useTranslation } from "react-i18next";

export default function Sites() {
  const { tc } = useTc();
  const { t } = useTranslation();
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Site[]>([]);
  const [controllers, setControllers] = useState<Controller[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [editingSite, setEditingSite] = useState<Site | null>(null);
  const [form] = Form.useForm();
  const deliveryMode = Form.useWatch("delivery_mode", form);

  async function load() {
    setLoading(true);
    try {
      const [s, c] = await Promise.all([
        api.get<Site[]>("/sites"),
        api.get<Controller[]>("/controllers"),
      ]);
      setRows(s.data);
      setControllers(c.data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  const controllerName = (id?: number) =>
    controllers.find((c) => c.id === id)?.name;

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post("/sites", values);
      message.success(toast.created);
      closeModal();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  async function onUpdate() {
    const values = await form.validateFields();
    if (!editingSite) return;
    const payload = { ...values };
    delete payload.code;
    if (payload.delivery_mode !== "controller") {
      payload.controller_id = null;
    }
    try {
      await api.patch(`/sites/${editingSite.id}`, payload);
      message.success(toast.saved);
      closeModal();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || toast.failed);
    }
  }

  function openCreate() {
    setEditingSite(null);
    form.resetFields();
    form.setFieldsValue({ delivery_mode: "direct" });
    setOpen(true);
  }

  function openEdit(site: Site) {
    setEditingSite(site);
    form.setFieldsValue({
      name: site.name,
      code: site.code,
      region: site.region,
      bgp_asn: site.bgp_asn,
      underlay_prefix: site.underlay_prefix,
      delivery_mode: site.delivery_mode || "direct",
      controller_id: site.controller_id,
    });
    setOpen(true);
  }

  function closeModal() {
    setOpen(false);
    setEditingSite(null);
    form.resetFields();
  }

  async function remove(id: number) {
    await api.delete(`/sites/${id}`);
    message.success(toast.deleted);
    load();
  }

  return (
    <PageCard
      title={page.sites}
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>{tc('新建站点')}</Button>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        {...dataTableProps()}
        locale={{ emptyText: tc("暂无站点 · 点击右上角新建") }}
        pagination={{
          pageSize: 12,
          hideOnSinglePage: true,
          showSizeChanger: false,
          showTotal: (n) => t("table.totalSites", { total: n }),
        }}
        columns={[
          { title: tc("编码"), dataIndex: "code", width: "10%", ellipsis: true },
          { title: tc("名称"), dataIndex: "name", width: "14%", ellipsis: true },
          { title: tc("区域"), dataIndex: "region", width: "10%", render: (v) => v || "—" },
          {
            title: "BGP ASN",
            dataIndex: "bgp_asn",
            width: "10%",
            render: (v) => (v ? <Tag>{v}</Tag> : "—"),
          },
          {
            title: tc('Underlay 网段'),
            dataIndex: "underlay_prefix",
            width: "14%",
            ellipsis: true,
            render: (v) => v || "—",
          },
          {
            title: tc('下发模式'),
            dataIndex: "delivery_mode",
            width: "18%",
            ellipsis: true,
            render: (m, r) =>
              m === "controller" ? (
                <Tag color="purple">{tc("控制器")}: {controllerName(r.controller_id) || "?"}</Tag>
              ) : (
                <Tag color="green">{tc('直连下发')}</Tag>
              ),
          },
          {
            title: tc('操作'),
            width: "10%",
            className: "table-actions",
            render: (_, r) => (
              <Space size={4}>
                <Button type="link" size="small" onClick={() => openEdit(r)}>
                  {action.edit}
                </Button>
                <Popconfirm title={tc('确认删除该站点?')} onConfirm={() => remove(r.id)}>
                  <Button type="link" size="small" danger>
                    {action.delete}
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal
        title={editingSite ? tc('编辑 Fabric 站点') : tc('新建 Fabric 站点')}
        open={open}
        onOk={editingSite ? onUpdate : onCreate}
        onCancel={closeModal}
        okText={editingSite ? action.save : action.create}
        {...formModalProps}
      >
        <Form form={form} layout="vertical" className="app-form">
          <Form.Item name="name" label={tc('站点名称')} rules={[{ required: true }]}>
            <Input placeholder={tc('例如 北京 Fabric PoP')} />
          </Form.Item>
          <Form.Item name="code" label={tc('编码')} rules={[{ required: true }]}>
            <Input placeholder={tc('例如 BJ-DC1')} disabled={!!editingSite} />
          </Form.Item>
          <Form.Item name="region" label={tc('区域')}>
            <Input placeholder={tc('例如 华北')} />
          </Form.Item>
          <Form.Item name="bgp_asn" label="BGP ASN">
            <InputNumber style={{ width: "100%" }} placeholder={tc('例如 65001')} />
          </Form.Item>
          <Form.Item name="underlay_prefix" label={tc('Underlay 网段')}>
            <Input placeholder={tc('例如 10.1.0.0/16')} />
          </Form.Item>
          <Form.Item name="delivery_mode" label={tc('下发模式')} initialValue="direct">
            <Select
              options={[
                { value: "direct", label: tc("直连下发 (NETCONF/CLI)") },
                { value: "controller", label: tc("控制器北向下发") },
              ]}
            />
          </Form.Item>
          {deliveryMode === "controller" && (
            <Form.Item name="controller_id" label={tc('关联控制器')} rules={[{ required: true }]}>
              <Select
                options={controllers.map((c) => ({
                  value: c.id,
                  label:
                    c.type === "bugis"
                      ? `${c.name} (${tc("内置 · 推荐")})`
                      : c.name,
                }))}
              />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </PageCard>
  );
}

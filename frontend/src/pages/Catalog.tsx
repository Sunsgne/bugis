import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  App as AntApp,
  Popconfirm,
  Typography,
} from "antd";
import { EyeOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import type { Offering, Paginated } from "../api/types";
import { buildListQuery, tablePagination } from "../utils/table";

const { Text, Paragraph } = Typography;

const SERVICE_LABEL: Record<string, string> = {
  l2vpn_evpn: "EVPN L2VPN",
  l3vpn_evpn: "EVPN L3VPN",
  evpn_vpws: "EVPN-VPWS",
  dci: "DCI 互联",
  remote_ipt: "Remote IPT",
};
const TIER_LABEL: Record<string, string> = {
  gold: "金牌",
  silver: "银牌",
  bronze: "铜牌",
};
const TIER_COLOR: Record<string, string> = {
  gold: "gold",
  silver: "default",
  bronze: "orange",
};

export default function Catalog() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Offering[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [serviceType, setServiceType] = useState<string | undefined>();
  const [tier, setTier] = useState<string | undefined>();
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>();
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<Offering | null>(null);
  const [form] = Form.useForm();

  async function load(
    p = page,
    ps = pageSize,
    q = search,
    svc = serviceType,
    t = tier,
    active = activeFilter,
  ) {
    setLoading(true);
    try {
      const { data } = await api.get<Paginated<Offering>>(
        `/offerings${buildListQuery({
          page: p,
          page_size: ps,
          q: q || undefined,
          service_type: svc,
          tier: t,
          active: active,
        })}`,
      );
      setRows(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, pageSize]);

  function applyFilters() {
    setPage(1);
    load(1, pageSize, search, serviceType, tier, activeFilter);
  }

  function resetFilters() {
    setSearch("");
    setServiceType(undefined);
    setTier(undefined);
    setActiveFilter(undefined);
    setPage(1);
    load(1, pageSize, "", undefined, undefined, undefined);
  }

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post("/offerings", values);
      message.success("套餐已创建");
      setOpen(false);
      form.resetFields();
      applyFilters();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function remove(id: number) {
    await api.delete(`/offerings/${id}`);
    message.success("已删除");
    load();
  }

  async function toggleActive(o: Offering, active: boolean) {
    await api.patch(`/offerings/${o.id}`, { active });
    message.success(active ? "已上架" : "已下架");
    load();
  }

  return (
    <Card
      title="服务套餐"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新建套餐
        </Button>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="套餐是什么？"
        description={
          <Paragraph style={{ marginBottom: 0 }}>
            套餐是<strong>开通专线时的参数模板</strong>，不是已售出的业务实例。新建专线时选择套餐，
            系统自动预填<strong>业务类型、带宽、SLA、CoS、MTU、等级</strong> 等字段，保证同类业务配置一致。
            万级套餐场景下请用下方搜索与分类筛选；点击「明细」查看完整参数。
          </Paragraph>
        }
      />

      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          allowClear
          placeholder="搜索套餐名称或编码"
          style={{ width: 260 }}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onSearch={applyFilters}
          enterButton={<SearchOutlined />}
        />
        <Select
          allowClear
          placeholder="业务类型"
          style={{ width: 150 }}
          value={serviceType}
          onChange={setServiceType}
          options={Object.entries(SERVICE_LABEL).map(([value, label]) => ({ value, label }))}
        />
        <Select
          allowClear
          placeholder="等级"
          style={{ width: 120 }}
          value={tier}
          onChange={setTier}
          options={[
            { value: "gold", label: "金牌 gold" },
            { value: "silver", label: "银牌 silver" },
            { value: "bronze", label: "铜牌 bronze" },
          ]}
        />
        <Select
          allowClear
          placeholder="上架状态"
          style={{ width: 120 }}
          value={activeFilter}
          onChange={setActiveFilter}
          options={[
            { value: true, label: "已上架" },
            { value: false, label: "已下架" },
          ]}
        />
        <Button type="primary" onClick={applyFilters}>
          筛选
        </Button>
        <Button onClick={resetFilters}>重置</Button>
        <Text type="secondary">共 {total.toLocaleString()} 个套餐</Text>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        size="middle"
        scroll={{ x: 1100 }}
        pagination={tablePagination(total, page, pageSize, (p, ps) => {
          setPage(p);
          setPageSize(ps);
        })}
        columns={[
          { title: "套餐名称", dataIndex: "name", width: 180, ellipsis: true },
          {
            title: "编码",
            dataIndex: "code",
            width: 120,
            render: (c) => <Tag>{c}</Tag>,
          },
          {
            title: "业务类型",
            dataIndex: "service_type",
            width: 130,
            render: (s) => <Tag color="geekblue">{SERVICE_LABEL[s] || s}</Tag>,
          },
          {
            title: "带宽",
            dataIndex: "bandwidth_mbps",
            width: 110,
            render: (b) => `${Number(b).toLocaleString()} Mbps`,
          },
          {
            title: "SLA",
            dataIndex: "sla_target",
            width: 90,
            render: (s) => (s ? `${s}%` : "-"),
          },
          { title: "CoS", dataIndex: "cos", width: 80, render: (c) => c || "-" },
          { title: "MTU", dataIndex: "mtu", width: 80 },
          {
            title: "等级",
            dataIndex: "tier",
            width: 100,
            render: (t) =>
              t ? (
                <Tag color={TIER_COLOR[t]}>
                  {TIER_LABEL[t] || t} {t}
                </Tag>
              ) : (
                "-"
              ),
          },
          {
            title: "状态",
            dataIndex: "active",
            width: 100,
            render: (active, r) => (
              <Switch
                checked={active}
                checkedChildren="上架"
                unCheckedChildren="下架"
                onChange={(v) => toggleActive(r, v)}
              />
            ),
          },
          {
            title: "说明",
            dataIndex: "description",
            ellipsis: true,
            render: (d) => d || <Text type="secondary">-</Text>,
          },
          {
            title: "操作",
            width: 120,
            fixed: "right",
            render: (_, r) => (
              <Space>
                <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => setDetail(r)}>
                  明细
                </Button>
                <Popconfirm title="删除该套餐?" onConfirm={() => remove(r.id)}>
                  <Button type="link" danger size="small">
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={detail ? `套餐明细 · ${detail.name}` : "套餐明细"}
        width={520}
        open={!!detail}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="套餐名称">{detail.name}</Descriptions.Item>
            <Descriptions.Item label="编码">
              <Tag>{detail.code}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="业务类型">
              <Tag color="geekblue">{SERVICE_LABEL[detail.service_type] || detail.service_type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="带宽">{detail.bandwidth_mbps.toLocaleString()} Mbps</Descriptions.Item>
            <Descriptions.Item label="SLA">{detail.sla_target ? `${detail.sla_target}%` : "-"}</Descriptions.Item>
            <Descriptions.Item label="CoS">{detail.cos || "-"}</Descriptions.Item>
            <Descriptions.Item label="MTU">{detail.mtu}</Descriptions.Item>
            <Descriptions.Item label="等级">
              {detail.tier ? (
                <Tag color={TIER_COLOR[detail.tier]}>
                  {TIER_LABEL[detail.tier] || detail.tier} ({detail.tier})
                </Tag>
              ) : (
                "-"
              )}
            </Descriptions.Item>
            <Descriptions.Item label="上架状态">
              <Tag color={detail.active ? "green" : "default"}>{detail.active ? "已上架" : "已下架"}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="说明">{detail.description || "-"}</Descriptions.Item>
            {"created_at" in detail && (detail as Offering & { created_at?: string }).created_at && (
              <Descriptions.Item label="创建时间">
                {dayjs((detail as Offering & { created_at?: string }).created_at).format("YYYY-MM-DD HH:mm")}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>

      <Modal title="新建套餐" open={open} onOk={onCreate} onCancel={() => setOpen(false)} width={560}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            service_type: "l2vpn_evpn",
            bandwidth_mbps: 1000,
            mtu: 9000,
            tier: "silver",
            active: true,
          }}
        >
          <Form.Item name="name" label="套餐名称" rules={[{ required: true }]}>
            <Input placeholder="例如 银牌混合云接入 1G" />
          </Form.Item>
          <Form.Item
            name="code"
            label="编码"
            rules={[{ required: true }]}
            extra="开通专线时下拉显示此编码，建议简短唯一"
          >
            <Input placeholder="例如 SILVER-HC-1G" />
          </Form.Item>
          <Form.Item name="service_type" label="业务类型">
            <Select
              options={Object.entries(SERVICE_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="bandwidth_mbps" label="带宽 (Mbps)">
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="sla_target" label="SLA (%)">
            <Input placeholder="99.99" />
          </Form.Item>
          <Form.Item name="cos" label="CoS / DSCP">
            <Input placeholder="例如 ef / af41" />
          </Form.Item>
          <Form.Item name="mtu" label="MTU">
            <InputNumber min={576} max={9216} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="tier" label="等级">
            <Select
              options={[
                { value: "gold", label: "金牌 gold" },
                { value: "silver", label: "银牌 silver" },
                { value: "bronze", label: "铜牌 bronze" },
              ]}
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="面向客户的套餐说明，如适用场景、交付标准" />
          </Form.Item>
          <Form.Item name="active" label="立即上架" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

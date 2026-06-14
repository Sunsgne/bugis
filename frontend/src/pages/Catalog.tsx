import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Tag,
  App as AntApp,
  Popconfirm,
  Statistic,
} from "antd";
import { PlusOutlined, CrownOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Offering } from "../api/types";

const SERVICE_LABEL: Record<string, string> = {
  l2vpn_evpn: "EVPN L2VPN",
  l3vpn_evpn: "EVPN L3VPN",
  evpn_vpws: "EVPN-VPWS",
  dci: "DCI 互联",
};
const TIER_COLOR: Record<string, string> = {
  gold: "gold",
  silver: "default",
  bronze: "orange",
};

export default function Catalog() {
  const { message } = AntApp.useApp();
  const [rows, setRows] = useState<Offering[]>([]);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    const { data } = await api.get<Offering[]>("/offerings");
    setRows(data);
  }
  useEffect(() => {
    load();
  }, []);

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post("/offerings", values);
      message.success("套餐已创建");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function remove(id: number) {
    await api.delete(`/offerings/${id}`);
    message.success("已删除");
    load();
  }

  return (
    <Card
      title="服务套餐目录"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          新建套餐
        </Button>
      }
    >
      <Row gutter={[16, 16]}>
        {rows.map((o) => (
          <Col xs={24} sm={12} md={8} lg={6} key={o.id}>
            <Card
              type="inner"
              title={
                <span>
                  {o.tier === "gold" && <CrownOutlined style={{ color: "#faad14" }} />}{" "}
                  {o.name}
                </span>
              }
              extra={<Tag color={TIER_COLOR[o.tier || ""]}>{o.tier || "-"}</Tag>}
              actions={[
                <Popconfirm title="删除该套餐?" onConfirm={() => remove(o.id)} key="del">
                  <span style={{ color: "#cf1322" }}>删除</span>
                </Popconfirm>,
              ]}
            >
              <Statistic
                value={o.bandwidth_mbps}
                suffix="Mbps"
                valueStyle={{ color: "#1677ff", fontSize: 22 }}
              />
              <div style={{ marginTop: 8 }}>
                <Tag color="geekblue">{SERVICE_LABEL[o.service_type] || o.service_type}</Tag>
                {o.sla_target && <Tag>SLA {o.sla_target}%</Tag>}
                {o.cos && <Tag>CoS {o.cos}</Tag>}
              </div>
              <div style={{ marginTop: 8, color: "#888", fontSize: 12, minHeight: 32 }}>
                {o.description}
              </div>
              <Tag color="blue" style={{ marginTop: 4 }}>
                {o.code}
              </Tag>
            </Card>
          </Col>
        ))}
      </Row>

      <Modal title="新建套餐" open={open} onOk={onCreate} onCancel={() => setOpen(false)}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ service_type: "l2vpn_evpn", bandwidth_mbps: 1000, mtu: 9000, tier: "silver" }}
        >
          <Form.Item name="name" label="套餐名称" rules={[{ required: true }]}>
            <Input placeholder="例如 金牌混合云接入" />
          </Form.Item>
          <Form.Item name="code" label="编码" rules={[{ required: true }]}>
            <Input placeholder="例如 GOLD-HC" />
          </Form.Item>
          <Form.Item name="service_type" label="业务类型">
            <Select options={Object.entries(SERVICE_LABEL).map(([value, label]) => ({ value, label }))} />
          </Form.Item>
          <Form.Item name="bandwidth_mbps" label="带宽 (Mbps)">
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="sla_target" label="SLA (%)">
            <Input placeholder="99.99" />
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
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

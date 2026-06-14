import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  App as AntApp,
  Popconfirm,
  Descriptions,
  Drawer,
  Collapse,
  Timeline,
} from "antd";
import {
  PlusOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  MinusCircleOutlined,
  EditOutlined,
  DownloadOutlined,
  HistoryOutlined,
  RadarChartOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import type { Circuit, Device, Offering, Tenant } from "../api/types";

const SERVICE_LABEL: Record<string, string> = {
  l2vpn_evpn: "EVPN L2VPN",
  l3vpn_evpn: "EVPN L3VPN",
  evpn_vpws: "EVPN-VPWS",
  dci: "DCI 互联",
};
const STATUS_COLOR: Record<string, string> = {
  draft: "default",
  pending: "gold",
  provisioning: "processing",
  active: "green",
  degraded: "orange",
  suspended: "volcano",
  decommissioned: "default",
  failed: "red",
};

export default function Circuits() {
  const { message, modal } = AntApp.useApp();
  const [rows, setRows] = useState<Circuit[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const [modifyForm] = Form.useForm();
  const [modifyTarget, setModifyTarget] = useState<Circuit | null>(null);
  const [historyCircuit, setHistoryCircuit] = useState<Circuit | null>(null);
  const [history, setHistory] = useState<any>(null);
  const [diffText, setDiffText] = useState<Record<number, string>>({});

  async function load() {
    setLoading(true);
    try {
      const [c, t, d, o] = await Promise.all([
        api.get<Circuit[]>("/circuits"),
        api.get<Tenant[]>("/tenants"),
        api.get<Device[]>("/devices"),
        api.get<Offering[]>("/offerings?active=true"),
      ]);
      setRows(c.data);
      setTenants(t.data);
      setDevices(d.data);
      setOfferings(o.data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  const tenantName = (id: number) => tenants.find((t) => t.id === id)?.name || id;
  const deviceName = (id: number) => devices.find((d) => d.id === id)?.name || id;

  async function onCreate() {
    const values = await form.validateFields();
    try {
      await api.post("/circuits", values);
      message.success("专线已创建（草稿），可点击开通下发配置");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    }
  }

  async function runProvision(c: Circuit) {
    try {
      const { data } = await api.post(`/work-orders/provision/${c.id}`);
      if (data.status === "failed") {
        message.error(`开通工单 ${data.code} 失败（预检未通过）`);
      } else {
        message.success(`开通工单 ${data.code}: ${data.status}`);
      }
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "开通失败");
    }
  }

  async function provision(c: Circuit) {
    // Pre-flight compliance check before provisioning.
    const { data: v } = await api.get(`/circuits/${c.id}/validate`);
    if (!v.ok) {
      modal.confirm({
        title: `预检发现 ${v.errors} 个错误 / ${v.warnings} 个告警`,
        width: 560,
        content: (
          <div style={{ maxHeight: 320, overflow: "auto" }}>
            {v.issues.map((i: any, idx: number) => (
              <div key={idx} style={{ marginBottom: 4 }}>
                <Tag color={i.level === "error" ? "red" : "orange"}>{i.level}</Tag>
                <span>{i.message}</span>
              </div>
            ))}
            {v.errors > 0 && (
              <div style={{ color: "#cf1322", marginTop: 8 }}>
                存在错误，下发将被编排引擎阻断。
              </div>
            )}
          </div>
        ),
        okText: v.errors > 0 ? "仍尝试开通" : "继续开通",
        onOk: () => runProvision(c),
      });
      return;
    }
    runProvision(c);
  }

  async function decommission(c: Circuit) {
    try {
      const { data } = await api.post(
        `/work-orders/provision/${c.id}?wo_type=decommission`
      );
      message.success(`拆除工单 ${data.code}: ${data.status}`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "拆除失败");
    }
  }

  async function doModify() {
    if (!modifyTarget) return;
    const v = await modifyForm.validateFields();
    try {
      await api.patch(`/circuits/${modifyTarget.id}`, { bandwidth_mbps: v.bandwidth_mbps });
      const { data } = await api.post(
        `/work-orders/provision/${modifyTarget.id}?wo_type=modify`
      );
      message.success(`变更工单 ${data.code}: ${data.status}`);
      setModifyTarget(null);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "变更失败");
    }
  }

  async function probe(c: Circuit) {
    const hide = message.loading(`正在拨测 ${c.code} ...`, 0);
    try {
      const { data } = await api.post(`/circuits/${c.id}/probe`);
      hide();
      modal.info({
        title: `拨测结果 · ${data.circuit}`,
        width: 640,
        content: (
          <div>
            <div style={{ marginBottom: 8 }}>
              <Tag color={data.reachable ? "green" : "red"}>
                {data.reachable ? "可达" : "不可达"}
              </Tag>
              {data.rtt_ms != null && <Tag>RTT {data.rtt_ms} ms</Tag>}
              <Tag>抖动 {data.jitter_ms} ms</Tag>
              <Tag color={data.packet_loss_pct > 1 ? "red" : undefined}>
                丢包 {data.packet_loss_pct}%
              </Tag>
            </div>
            <Table
              size="small"
              rowKey="hop"
              pagination={false}
              dataSource={data.hops}
              columns={[
                { title: "跳", dataIndex: "hop", width: 50 },
                { title: "设备", dataIndex: "device" },
                { title: "厂商", dataIndex: "vendor", render: (v) => <Tag>{v}</Tag> },
                { title: "IP", dataIndex: "ip" },
                {
                  title: "RTT(ms)",
                  dataIndex: "rtt_ms",
                  render: (v) => (v == null ? "*" : v),
                },
                {
                  title: "状态",
                  dataIndex: "status",
                  render: (s) => (
                    <Tag color={s === "up" ? "green" : "red"}>{s}</Tag>
                  ),
                },
              ]}
            />
          </div>
        ),
      });
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || "拨测失败");
    }
  }

  async function openHistory(c: Circuit) {
    setHistoryCircuit(c);
    setDiffText({});
    const { data } = await api.get(`/circuits/${c.id}/config-history`);
    setHistory(data);
  }

  async function loadDiff(circuitId: number, deviceId: number) {
    const { data } = await api.get(
      `/circuits/${circuitId}/config-diff?device_id=${deviceId}`
    );
    setDiffText((prev) => ({ ...prev, [deviceId]: data.diff }));
  }

  async function preview(c: Circuit) {
    const wo = await api.post(`/work-orders`, { circuit_id: c.id, type: "provision" });
    const { data } = await api.get(`/work-orders/${wo.data.id}/preview`);
    modal.info({
      title: `配置预览 · ${c.code} (${c.name})`,
      width: 760,
      content: (
        <div style={{ maxHeight: 480, overflow: "auto" }}>
          {data.previews.map((p: any, i: number) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <Tag color="blue">{p.vendor.toUpperCase()}</Tag>
              <b>{p.device}</b> <Tag>{p.transport}</Tag>
              <pre className="config-pre">{p.config}</pre>
            </div>
          ))}
        </div>
      ),
    });
  }

  return (
    <Card
      title="专线管理"
      extra={
        <Space>
          <Button
            icon={<DownloadOutlined />}
            onClick={async () => {
              const { data } = await api.get("/bulk/circuits/export", {
                responseType: "text",
              });
              const blob = new Blob([data], { type: "text/csv" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "circuits.csv";
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            导出 CSV
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            新建专线
          </Button>
        </Space>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        expandable={{
          expandedRowRender: (r) => (
            <Descriptions size="small" column={3} bordered>
              <Descriptions.Item label="VNI">{r.vni}</Descriptions.Item>
              <Descriptions.Item label="VLAN">{r.vlan_id}</Descriptions.Item>
              <Descriptions.Item label="VRF">{r.vrf_name}</Descriptions.Item>
              <Descriptions.Item label="RD">{r.route_distinguisher}</Descriptions.Item>
              <Descriptions.Item label="RT">{r.route_target}</Descriptions.Item>
              <Descriptions.Item label="MTU">{r.mtu}</Descriptions.Item>
              <Descriptions.Item label="端点" span={3}>
                {r.endpoints.map((e) => (
                  <Tag key={e.id}>
                    {e.label}: {deviceName(e.device_id)} / {e.interface_name}
                  </Tag>
                ))}
              </Descriptions.Item>
            </Descriptions>
          ),
        }}
        columns={[
          { title: "编码", dataIndex: "code" },
          { title: "名称", dataIndex: "name" },
          { title: "租户", render: (_, r) => tenantName(r.tenant_id) },
          {
            title: "业务类型",
            dataIndex: "service_type",
            render: (s) => <Tag color="geekblue">{SERVICE_LABEL[s] || s}</Tag>,
          },
          { title: "VNI", dataIndex: "vni" },
          {
            title: "带宽",
            dataIndex: "bandwidth_mbps",
            render: (b) => `${b} Mbps`,
          },
          { title: "SLA", dataIndex: "sla_target", render: (s) => s && <Tag>{s}%</Tag> },
          {
            title: "状态",
            dataIndex: "status",
            render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
          },
          {
            title: "操作",
            width: 240,
            render: (_, r) => (
              <Space>
                <Tooltip title="一键开通（下发配置, dry-run）">
                  <Button
                    size="small"
                    type="primary"
                    icon={<ThunderboltOutlined />}
                    onClick={() => provision(r)}
                    disabled={r.status === "active"}
                  >
                    开通
                  </Button>
                </Tooltip>
                <Tooltip title="变更带宽">
                  <Button
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => {
                      setModifyTarget(r);
                      modifyForm.setFieldsValue({ bandwidth_mbps: r.bandwidth_mbps });
                    }}
                  />
                </Tooltip>
                <Tooltip title="预览各厂商配置">
                  <Button size="small" icon={<EyeOutlined />} onClick={() => preview(r)} />
                </Tooltip>
                <Tooltip title="端到端拨测">
                  <Button
                    size="small"
                    icon={<RadarChartOutlined />}
                    onClick={() => probe(r)}
                    disabled={r.status !== "active"}
                  />
                </Tooltip>
                <Tooltip title="配置历史与版本对比">
                  <Button size="small" icon={<HistoryOutlined />} onClick={() => openHistory(r)} />
                </Tooltip>
                <Popconfirm title="确认拆除该专线?" onConfirm={() => decommission(r)}>
                  <Button size="small" danger icon={<MinusCircleOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <CreateModal
        open={open}
        form={form}
        tenants={tenants}
        devices={devices}
        offerings={offerings}
        onOk={onCreate}
        onCancel={() => setOpen(false)}
      />
      <Modal
        title={`变更带宽 · ${modifyTarget?.code || ""}`}
        open={!!modifyTarget}
        onOk={doModify}
        onCancel={() => setModifyTarget(null)}
        okText="提交变更并下发"
      >
        <Form form={modifyForm} layout="vertical">
          <Form.Item
            name="bandwidth_mbps"
            label="新带宽 (Mbps)"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <div style={{ color: "#888", fontSize: 12 }}>
            变更将创建 MODIFY 工单并重新下发各厂商 QoS / 限速配置。
          </div>
        </Form>
      </Modal>

      <Drawer
        title={`配置历史 · ${historyCircuit?.code || ""}`}
        width={760}
        open={!!historyCircuit}
        onClose={() => setHistoryCircuit(null)}
      >
        {history && (
          <Collapse
            items={(history.devices || []).map((d: any) => ({
              key: d.device_id,
              label: (
                <span>
                  <b>{d.device}</b>{" "}
                  <Tag>{d.versions.length} 个版本</Tag>
                </span>
              ),
              children: (
                <>
                  <Button
                    size="small"
                    type="primary"
                    ghost
                    style={{ marginBottom: 8 }}
                    onClick={() => loadDiff(historyCircuit!.id, d.device_id)}
                  >
                    对比最近两个版本
                  </Button>
                  {diffText[d.device_id] && (
                    <pre className="config-pre">
                      {diffText[d.device_id].split("\n").map((line, i) => (
                        <div
                          key={i}
                          style={{
                            color: line.startsWith("+")
                              ? "#52c41a"
                              : line.startsWith("-")
                              ? "#ff7875"
                              : line.startsWith("@@")
                              ? "#1677ff"
                              : undefined,
                          }}
                        >
                          {line}
                        </div>
                      ))}
                    </pre>
                  )}
                  <Timeline
                    style={{ marginTop: 12 }}
                    items={d.versions
                      .slice()
                      .reverse()
                      .map((v: any) => ({
                        color: v.status.includes("fail") ? "red" : "blue",
                        children: (
                          <div>
                            <Tag>{v.work_order}</Tag>
                            <Tag color="geekblue">{v.operation}</Tag>
                            <Tag>{v.status}</Tag>
                            <span style={{ color: "#888", fontSize: 12 }}>
                              {v.created_at?.replace("T", " ").slice(0, 19)}
                            </span>
                            <pre className="config-pre" style={{ maxHeight: 180 }}>
                              {v.rendered_config}
                            </pre>
                          </div>
                        ),
                      }))}
                  />
                </>
              ),
            }))}
          />
        )}
      </Drawer>
    </Card>
  );
}

function CreateModal({ open, form, tenants, devices, offerings, onOk, onCancel }: any) {
  function applyOffering(id: number) {
    const o = offerings.find((x: Offering) => x.id === id);
    if (!o) return;
    form.setFieldsValue({
      service_type: o.service_type,
      bandwidth_mbps: o.bandwidth_mbps,
      sla_target: o.sla_target,
    });
  }
  return (
    <Modal title="新建专线" open={open} onOk={onOk} onCancel={onCancel} width={680}>
      <Form
        form={form}
        layout="vertical"
        initialValues={{ service_type: "l2vpn_evpn", bandwidth_mbps: 100, mtu: 9000, endpoints: [{ label: "A" }, { label: "Z" }] }}
      >
        <Form.Item name="offering_id" label="选择套餐 (可选, 自动预填参数)">
          <Select
            allowClear
            placeholder="不使用套餐则手动填写下方参数"
            onChange={(v) => v && applyOffering(v)}
            options={offerings.map((o: Offering) => ({
              value: o.id,
              label: `${o.tier ? `[${o.tier}] ` : ""}${o.name} · ${o.bandwidth_mbps}Mbps`,
            }))}
          />
        </Form.Item>
        <Space size="middle" style={{ display: "flex" }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]} style={{ flex: 1 }}>
            <Input placeholder="例如 银行北京-上海二层专线" />
          </Form.Item>
          <Form.Item name="tenant_id" label="租户" rules={[{ required: true }]} style={{ width: 200 }}>
            <Select
              options={tenants.map((t: Tenant) => ({ value: t.id, label: `${t.code} ${t.name}` }))}
            />
          </Form.Item>
        </Space>
        <Space size="middle" style={{ display: "flex" }}>
          <Form.Item name="service_type" label="业务类型" style={{ flex: 1 }}>
            <Select
              options={Object.entries(SERVICE_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="bandwidth_mbps" label="带宽(Mbps)" style={{ width: 140 }}>
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="sla_target" label="SLA(%)" style={{ width: 120 }}>
            <Input placeholder="99.95" />
          </Form.Item>
        </Space>

        <div style={{ fontWeight: 600, marginBottom: 8 }}>接入端点</div>
        <Form.List name="endpoints">
          {(fields, { add, remove }) => (
            <>
              {fields.map((field) => (
                <Space key={field.key} align="baseline" style={{ display: "flex" }}>
                  <Form.Item name={[field.name, "label"]} rules={[{ required: true }]}>
                    <Input placeholder="标签 A/Z" style={{ width: 80 }} />
                  </Form.Item>
                  <Form.Item name={[field.name, "device_id"]} rules={[{ required: true }]}>
                    <Select
                      style={{ width: 240 }}
                      placeholder="选择设备"
                      options={devices.map((d: Device) => ({
                        value: d.id,
                        label: `${d.name} (${d.vendor})`,
                      }))}
                    />
                  </Form.Item>
                  <Form.Item name={[field.name, "interface_name"]} rules={[{ required: true }]}>
                    <Input placeholder="接口 GE1/0/1" style={{ width: 140 }} />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(field.name)} />
                </Space>
              ))}
              <Button type="dashed" block icon={<PlusOutlined />} onClick={() => add({ label: "" })}>
                添加端点
              </Button>
            </>
          )}
        </Form.List>
      </Form>
    </Modal>
  );
}

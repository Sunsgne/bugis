import { useEffect, useState } from "react";
import { Button, Card, Col, Row, Select, Table, Tag, Typography, App as AntApp } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { WorkOrder } from "../api/types";
import { page } from "../constants/uiCopy";

const { Paragraph, Text } = Typography;

const WEBHOOK_EXAMPLE = `curl -X POST http://<host>/api/v1/integrations/webhook/provision \\
  -H "X-Webhook-Token: bugis-webhook-token" \\
  -H "Content-Type: application/json" \\
  -d '{
    "tenant_code": "BANK01",
    "name": "自动开通专线",
    "service_type": "l2vpn_evpn",
    "bandwidth_mbps": 300,
    "endpoints": [
      {"label": "A", "device_name": "BJ-LEAF-01", "interface_name": "GE1/0/5"},
      {"label": "Z", "device_name": "SH-LEAF-01", "interface_name": "GE1/0/5"}
    ]
  }'`;

function download(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Integrations() {
  const { message } = AntApp.useApp();
  const [drivers, setDrivers] = useState<Record<string, any>>({});
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [selectedWo, setSelectedWo] = useState<number | null>(null);

  async function load() {
    const [cat, wos] = await Promise.all([
      api.get("/integrations/catalog"),
      api.get<WorkOrder[]>("/work-orders"),
    ]);
    setDrivers(cat.data.drivers);
    setWorkOrders(wos.data);
  }
  useEffect(() => {
    load();
  }, []);

  async function downloadInventory() {
    const { data } = await api.get("/integrations/ansible/inventory", {
      responseType: "text",
    });
    download("inventory.ini", data);
    message.success("Inventory 已导出");
  }

  async function downloadPlaybook() {
    if (!selectedWo) return message.warning("请先选择工单");
    const { data } = await api.get(`/work-orders/${selectedWo}/ansible`);
    download(`playbook-${data.work_order}.yml`, data.playbook);
    download(`inventory-${data.work_order}.ini`, data.inventory);
    message.success("Playbook · Inventory 已导出");
  }

  const driverRows = Object.entries(drivers).map(([vendor, d]: any) => ({
    vendor,
    ...d,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="北向 Webhook · StackStorm / ITSM">
            <Paragraph type="secondary">
              外部编排系统携带 <Text code>X-Webhook-Token</Text> 即可触发 Circuit 一键开通。
            </Paragraph>
            <pre className="config-pre">{WEBHOOK_EXAMPLE}</pre>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Ansible 编排导出">
            <Paragraph type="secondary">
              基于厂商官方 Collection（h3c.comware / huawei.datacom / cisco.iosxr /
              junipernetworks.junos / arista.eos）导出 Inventory 与 Playbook。
            </Paragraph>
            <Button
              icon={<DownloadOutlined />}
              onClick={downloadInventory}
              style={{ marginBottom: 12 }}
            >
              导出全量 Inventory
            </Button>
            <div style={{ display: "flex", gap: 8 }}>
              <Select
                style={{ flex: 1 }}
                placeholder="选择工单导出 Playbook"
                value={selectedWo ?? undefined}
                onChange={setSelectedWo}
                options={workOrders.map((w) => ({
                  value: w.id,
                  label: `${w.code} · ${w.title}`,
                }))}
              />
              <Button type="primary" icon={<DownloadOutlined />} onClick={downloadPlaybook}>
                导出 Playbook
              </Button>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title={`${page.integrations} · 南向驱动`}>
        <Table
          rowKey="vendor"
          pagination={false}
          dataSource={driverRows}
          columns={[
            {
              title: "厂商",
              dataIndex: "vendor",
              render: (v) => <Tag color="blue">{v.toUpperCase()}</Tag>,
            },
            {
              title: "Overlay 技术",
              dataIndex: "overlay_tech",
              render: (o) => (
                <Tag color={o === "vxlan_evpn" ? "blue" : "purple"}>
                  {o === "vxlan_evpn" ? "BGP EVPN VXLAN" : "SR-MPLS EVPN"}
                </Tag>
              ),
            },
            { title: "传输方式", dataIndex: "transport", render: (t) => <Tag>{t}</Tag> },
          ]}
        />
      </Card>
    </div>
  );
}

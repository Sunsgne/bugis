import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Drawer,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  App as AntApp,
} from "antd";
import { DownloadOutlined, EyeOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { WorkOrder } from "../api/types";
import { usePlatformSettings } from "../hooks/usePlatformSettings";
import { dataTableProps, TABLE_SCROLL } from "../utils/table";

const { Paragraph, Text } = Typography;

const STATUS_LABEL: Record<string, string> = {
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  draft: "草稿",
  pending: "待审批",
  approved: "已批准",
  executing: "执行中",
};

function isExportableWo(w: WorkOrder): boolean {
  return Boolean(w.config_jobs?.some((j) => j.rendered_config));
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Integrations({ embedded }: { embedded?: boolean }) {
  const { message } = AntApp.useApp();
  const { platform } = usePlatformSettings();
  const [drivers, setDrivers] = useState<Record<string, any>>({});
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [selectedWo, setSelectedWo] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [preview, setPreview] = useState<{ inventory: string; playbook: string; code: string } | null>(
    null,
  );

  const exportable = useMemo(() => workOrders.filter(isExportableWo), [workOrders]);
  const selected = workOrders.find((w) => w.id === selectedWo);

  const webhookExample = useMemo(() => {
    const host = typeof window !== "undefined" ? window.location.origin : "http://<host>";
    const token = platform?.webhook_token || "bugis-webhook-token";
    return `curl -X POST ${host}/api/v1/integrations/webhook/provision \\
  -H "X-Webhook-Token: ${token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "tenant_code": "BANK01",
    "name": "自动开通专线",
    "service_type": "l2vpn_evpn",
    "bandwidth_mbps": 300,
    "auto_provision": true,
    "endpoints": [
      {"label": "A", "device_name": "BJ-LEAF-01", "interface_name": "GE1/0/5"},
      {"label": "Z", "device_name": "SH-LEAF-01", "interface_name": "GE1/0/5"}
    ]
  }'`;
  }, [platform?.webhook_token]);

  async function load() {
    setLoading(true);
    try {
      const [cat, wos] = await Promise.all([
        api.get("/integrations/catalog"),
        api.get<WorkOrder[]>("/work-orders"),
      ]);
      setDrivers(cat.data.drivers);
      const list = wos.data;
      setWorkOrders(list);
      const first = list.find(isExportableWo);
      setSelectedWo((prev) => {
        if (prev && list.some((w) => w.id === prev && isExportableWo(w))) return prev;
        return first?.id ?? null;
      });
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "加载集成数据失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function downloadInventory() {
    try {
      const { data } = await api.get("/integrations/ansible/inventory", { responseType: "text" });
      downloadBlob("inventory.ini", new Blob([data], { type: "text/plain" }));
      message.success("已下载 Ansible inventory");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "下载失败");
    }
  }

  async function previewPlaybook() {
    if (!selectedWo) return message.warning("请选择工单");
    const wo = workOrders.find((w) => w.id === selectedWo);
    if (!wo || !isExportableWo(wo)) {
      return message.warning("该工单无可导出配置，请选择已完成的开通/变更工单");
    }
    try {
      const { data } = await api.get(`/work-orders/${selectedWo}/ansible`);
      setPreview({ inventory: data.inventory, playbook: data.playbook, code: data.work_order });
      setPreviewOpen(true);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "预览失败");
    }
  }

  async function downloadPlaybook() {
    if (!selectedWo) return message.warning("请选择工单");
    if (!selected || !isExportableWo(selected)) {
      return message.warning("该工单无可导出配置（已取消/未执行的工单无法导出）");
    }
    setExporting(true);
    try {
      const { data } = await api.get(`/work-orders/${selectedWo}/ansible/download`, {
        responseType: "blob",
      });
      downloadBlob(`ansible-${selected.code}.zip`, data);
      message.success("已下载 Ansible 压缩包（inventory + playbook + 设备配置）");
    } catch (e: any) {
      const detail = e?.response?.data;
      if (detail instanceof Blob) {
        const text = await detail.text();
        try {
          message.error(JSON.parse(text).detail || "导出失败");
        } catch {
          message.error("导出失败");
        }
      } else {
        message.error(detail?.detail || "导出失败");
      }
    } finally {
      setExporting(false);
    }
  }

  const driverRows = Object.entries(drivers).map(([vendor, d]: any) => ({
    vendor,
    ...d,
  }));

  const content = (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card title="北向 Webhook 接入 (StackStorm / ITSM)" loading={loading}>
            <Paragraph type="secondary">
              外部编排系统携带 <Text code>X-Webhook-Token</Text>（在上方保存）触发专线自动开通。
              设置 <Text code>auto_provision: true</Text> 可创建后立即执行工单。
            </Paragraph>
            <pre className="config-pre">{webhookExample}</pre>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="Ansible 编排导出" loading={loading}>
            <Paragraph type="secondary">
              从<strong>已完成且含配置快照</strong>的工单导出 inventory、playbook 及各设备 CLI 配置。
              基于厂商 Collection（h3c.comware / huawei.datacom / cisco.iosxr / juniper / arista.eos）。
            </Paragraph>
            {exportable.length === 0 ? (
              <Alert
                type="warning"
                showIcon
                message="暂无可导出工单"
                description="请先在「专线开通」完成一条专线的开通工单（状态 completed），再回来导出。"
                style={{ marginBottom: 12 }}
              />
            ) : (
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 12 }}
                message={`${exportable.length} 个工单可导出`}
                description="已取消、草稿或未执行的工单不会出现在可选列表中。"
              />
            )}
            <Button
              icon={<DownloadOutlined />}
              onClick={downloadInventory}
              style={{ marginBottom: 12 }}
              block
            >
              下载全量 Inventory
            </Button>
            <Space.Compact style={{ width: "100%" }}>
              <Select
                style={{ flex: 1 }}
                placeholder="选择已完成的工单"
                value={selectedWo ?? undefined}
                onChange={setSelectedWo}
                showSearch
                optionFilterProp="label"
                options={workOrders.map((w) => ({
                  value: w.id,
                  disabled: !isExportableWo(w),
                  label: `${w.code} · ${w.title} · ${STATUS_LABEL[w.status] || w.status}`,
                }))}
              />
              <Button icon={<EyeOutlined />} onClick={previewPlaybook} disabled={!selectedWo}>
                预览
              </Button>
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                loading={exporting}
                onClick={downloadPlaybook}
                disabled={!selectedWo || !selected || !isExportableWo(selected)}
              >
                导出 ZIP
              </Button>
            </Space.Compact>
          </Card>
        </Col>
      </Row>

      <Card title="南向驱动目录">
        <Table
          {...dataTableProps(TABLE_SCROLL.lg)}
          rowKey="vendor"
          pagination={false}
          loading={loading}
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

      <Drawer
        title={preview ? `Ansible 预览 · ${preview.code}` : "Ansible 预览"}
        width={720}
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        extra={
          preview && (
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              loading={exporting}
              onClick={downloadPlaybook}
            >
              下载 ZIP
            </Button>
          )
        }
      >
        {preview && (
          <Tabs
            items={[
              {
                key: "playbook",
                label: "Playbook",
                children: <pre className="config-pre config-pre-lg">{preview.playbook}</pre>,
              },
              {
                key: "inventory",
                label: "Inventory",
                children: <pre className="config-pre config-pre-lg">{preview.inventory}</pre>,
              },
            ]}
          />
        )}
      </Drawer>
    </div>
  );

  if (embedded) return content;

  return <Card title="集成中心">{content}</Card>;
}

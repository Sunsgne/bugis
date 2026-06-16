import { useEffect, useState } from "react";
import { Button, Card, Table, Tag, Tabs, App as AntApp, Empty, Descriptions, Typography } from "antd";
import { CloudUploadOutlined, DiffOutlined, ReloadOutlined, BookOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import { configPreviewModalProps, ConfigPreviewPre } from "../utils/configPreview";
import { dataTableProps } from "../utils/table";

const VENDOR_COLOR: Record<string, string> = {
  h3c: "blue", huawei: "red", juniper: "green", arista: "orange", cisco: "purple", frr: "cyan",
};

function ColoredDiff({ text }: { text: string }) {
  return (
    <pre className="config-pre config-pre-fill">
      {text.split("\n").map((line, i) => (
        <div key={i} style={{
          color: line.startsWith("+") ? "#52c41a" : line.startsWith("-") ? "#ff7875"
            : line.startsWith("@@") ? "#1677ff" : undefined,
        }}>{line}</div>
      ))}
    </pre>
  );
}

export default function ConfigManagement() {
  const { message, modal } = AntApp.useApp();
  const [devices, setDevices] = useState<any[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [running, setRunning] = useState<string>("");
  const [snaps, setSnaps] = useState<any[]>([]);
  const [diff, setDiff] = useState<string>("");
  const [drift, setDrift] = useState<string>("");
  const [learned, setLearned] = useState<any>(null);

  async function loadDevices() {
    const { data } = await api.get("/config/devices");
    setDevices(data);
    if (!sel && data.length) select(data[0].device_id);
  }
  useEffect(() => { loadDevices(); }, []);

  async function select(id: number) {
    setSel(id);
    const [r, s, ls] = await Promise.all([
      api.get(`/config/devices/${id}/running`),
      api.get(`/config/devices/${id}/snapshots`),
      api.get(`/devices/${id}/learned-state`).catch(() => ({ data: null })),
    ]);
    setRunning(r.data.content);
    setSnaps(s.data);
    setDiff("");
    setDrift("");
    setLearned(ls.data);
  }

  async function backup() {
    if (!sel) return;
    const hide = message.loading("正在拉取设备 running-config...", 0);
    try {
      const { data } = await api.post(`/config/devices/${sel}/backup`);
      hide();
      const via = data.fetched_live
        ? "现网拉取"
        : `复用学习 v${data.from_learned_version}`;
      message.success(`备份完成 v${data.version} · ${data.lines} 行 · ${via}`);
      select(sel);
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || "备份失败");
    }
  }

  async function loadDrift() {
    if (!sel) return;
    try {
      const { data } = await api.get(`/config/devices/${sel}/drift`);
      setDrift(data.diff);
      setLearned((p: any) => ({ ...p, inventory: data.inventory }));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "暂无现网学习快照");
    }
  }

  async function runLearn() {
    if (!sel) return;
    const hide = message.loading("现网配置学习中...", 0);
    try {
      await api.post(`/devices/${sel}/learn`);
      hide();
      message.success("现网配置学习完成");
      select(sel);
      loadDevices();
    } catch (e: any) {
      hide();
      message.error(e?.response?.data?.detail || "学习失败");
    }
  }

  async function loadDiff() {
    if (!sel) return;
    const { data } = await api.get(`/config/devices/${sel}/diff`);
    setDiff(data.diff);
  }

  async function viewSnap(id: number) {
    const { data } = await api.get(`/config/devices/${sel}/snapshots/${id}`);
    modal.info({
      title: `配置快照 v${data.version}`,
      ...configPreviewModalProps,
      content: <ConfigPreviewPre>{data.content}</ConfigPreviewPre>,
    });
  }

  return (
    <div className="config-management-page">
      <Card
        className="config-panel-card"
        title="设备配置"
        extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadDevices} />}
      >
        <Table
          rowKey="device_id"
          size="small"
          pagination={false}
          dataSource={devices}
          onRow={(r) => ({ onClick: () => select(r.device_id), style: { cursor: "pointer" } })}
          rowClassName={(r) => (r.device_id === sel ? "ant-table-row-selected" : "")}
          {...dataTableProps()}
          columns={[
            { title: "设备", dataIndex: "name", width: "28%", ellipsis: true },
            { title: "厂商", dataIndex: "vendor", width: "16%", render: (v) => <Tag color={VENDOR_COLOR[v]}>{v}</Tag> },
            { title: "版本", dataIndex: "latest_version", width: "16%", render: (v) => (v ? `v${v}` : "-") },
            {
              title: "现网学习",
              dataIndex: "learned_version",
              width: "40%",
              render: (v, r) =>
                v ? (
                  <Tag color="orange">v{v} · {r.service_count ?? 0} 业务</Tag>
                ) : (
                  <Tag>未学习</Tag>
                ),
            },
          ]}
        />
      </Card>

      <Card
        className="config-panel-card"
        title="配置管理"
        extra={
          <Button.Group>
            <Button icon={<BookOutlined />} onClick={runLearn} disabled={!sel}>
              现网学习
            </Button>
            <Button type="primary" icon={<CloudUploadOutlined />} onClick={backup} disabled={!sel}>
              备份现网配置
            </Button>
          </Button.Group>
        }
      >
        {!sel ? (
          <Empty description="选择左侧设备" />
        ) : (
          <Tabs
            className="config-tabs"
            items={[
              {
                key: "running",
                label: "平台期望配置 (Desired)",
                children: (
                  <>
                    <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8, fontSize: 12 }}>
                      由平台纳管专线拼装的目标配置；与设备现网配置可能不同。备份请使用右上角「备份现网配置」。
                    </Typography.Text>
                    <pre className="config-pre config-pre-fill">{running}</pre>
                  </>
                ),
              },
              {
                key: "learned",
                label: "现网学习",
                children: learned?.has_learned_config ? (
                  <>
                    <Descriptions size="small" bordered column={2} style={{ marginBottom: 12 }}>
                      <Descriptions.Item label="学习版本">v{learned.latest_snapshot_version}</Descriptions.Item>
                      <Descriptions.Item label="学习时间">
                        {learned.latest_snapshot_at ? dayjs(learned.latest_snapshot_at).format("YYYY-MM-DD HH:mm:ss") : "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label="业务数">
                        {learned.inventory?.service_count ?? 0}
                      </Descriptions.Item>
                      <Descriptions.Item label="VLAN 数">
                        {learned.inventory?.vlan_ids?.length ?? 0}
                      </Descriptions.Item>
                      <Descriptions.Item label="漂移行数">{learned.drift_line_count ?? 0}</Descriptions.Item>
                    </Descriptions>
                    {learned.inventory?.l2_services?.length > 0 && (
                      <Table
                        size="small"
                        rowKey="name"
                        pagination={false}
                        style={{ marginBottom: 12 }}
                        dataSource={learned.inventory.l2_services}
                        {...dataTableProps()}
                        columns={[
                          { title: "业务", dataIndex: "name", width: "22%" },
                          { title: "VNI", dataIndex: "vni", width: "12%" },
                          { title: "RD", dataIndex: "rd", width: "18%" },
                          { title: "RT", dataIndex: "rt", width: "18%" },
                          {
                            title: "接口",
                            dataIndex: "interfaces",
                            width: "30%",
                            render: (v: string[]) => v?.join(", ") || "-",
                          },
                        ]}
                      />
                    )}
                    <Button size="small" icon={<DiffOutlined />} onClick={loadDrift}>
                      平台 vs 现网 配置漂移
                    </Button>
                    {drift && <ColoredDiff text={drift} />}
                  </>
                ) : (
                  <Empty description="尚未执行现网学习">
                    <Button type="primary" icon={<BookOutlined />} onClick={runLearn}>
                      立即学习
                    </Button>
                  </Empty>
                ),
              },
              {
                key: "history",
                label: `版本历史 (${snaps.length})`,
                children: (
                  <>
                    <Button size="small" icon={<DiffOutlined />} onClick={loadDiff} style={{ marginBottom: 8 }}>
                      对比最近两版
                    </Button>
                    {diff && <ColoredDiff text={diff} />}
                    <Table
                      size="small"
                      rowKey="id"
                      pagination={false}
                      dataSource={snaps}
                      {...dataTableProps()}
                      locale={{ emptyText: <Empty description="暂无快照，点击「备份现网配置」" /> }}
                      columns={[
                        { title: "版本", dataIndex: "version", width: "10%", render: (v) => `v${v}` },
                        {
                          title: "来源", dataIndex: "source", width: "14%",
                          render: (s) => (
                            <Tag
                              color={
                                s === "push" ? "green" : s === "learn" ? "orange" : "blue"
                              }
                            >
                              {s === "push"
                                ? "开通下发"
                                : s === "backup"
                                  ? "手动备份"
                                  : s === "learn"
                                    ? "现网学习"
                                    : s}
                            </Tag>
                          ),
                        },
                        { title: "行数", dataIndex: "lines", width: "10%" },
                        { title: "操作人", dataIndex: "created_by", width: "14%", ellipsis: true },
                        { title: "备注", dataIndex: "note", width: "22%", ellipsis: true },
                        { title: "时间", dataIndex: "created_at", width: "18%", render: (t) => (t ? dayjs(t).format("MM-DD HH:mm:ss") : "-") },
                        { title: "", width: "12%", render: (_, r) => <a onClick={() => viewSnap(r.id)}>查看</a> },
                      ]}
                    />
                  </>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}

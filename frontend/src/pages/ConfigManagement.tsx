import { useEffect, useState } from "react";
import { Button, Card, Col, Row, Table, Tag, Tabs, App as AntApp, Empty, Modal } from "antd";
import { CloudUploadOutlined, DiffOutlined, ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import { configPreviewModalProps, ConfigPreviewPre } from "../utils/configPreview";

const VENDOR_COLOR: Record<string, string> = {
  h3c: "blue", huawei: "red", juniper: "green", arista: "orange", cisco: "purple", frr: "cyan",
};

function ColoredDiff({ text }: { text: string }) {
  return (
    <pre className="config-pre">
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

  async function loadDevices() {
    const { data } = await api.get("/config/devices");
    setDevices(data);
    if (!sel && data.length) select(data[0].device_id);
  }
  useEffect(() => { loadDevices(); }, []);

  async function select(id: number) {
    setSel(id);
    const [r, s] = await Promise.all([
      api.get(`/config/devices/${id}/running`),
      api.get(`/config/devices/${id}/snapshots`),
    ]);
    setRunning(r.data.content);
    setSnaps(s.data);
    setDiff("");
  }

  async function backup() {
    if (!sel) return;
    await api.post(`/config/devices/${sel}/backup`);
    message.success("已生成配置备份快照");
    select(sel);
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
    <Row gutter={16}>
      <Col xs={24} md={7}>
        <Card title="设备配置" extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadDevices} />}>
          <Table
            rowKey="device_id"
            size="small"
            pagination={false}
            dataSource={devices}
            onRow={(r) => ({ onClick: () => select(r.device_id), style: { cursor: "pointer" } })}
            rowClassName={(r) => (r.device_id === sel ? "ant-table-row-selected" : "")}
            columns={[
              { title: "设备", dataIndex: "name" },
              { title: "厂商", dataIndex: "vendor", render: (v) => <Tag color={VENDOR_COLOR[v]}>{v}</Tag> },
              { title: "版本", dataIndex: "latest_version", render: (v) => (v ? `v${v}` : "-") },
            ]}
          />
        </Card>
      </Col>
      <Col xs={24} md={17}>
        <Card
          title="配置管理"
          extra={
            <Button type="primary" icon={<CloudUploadOutlined />} onClick={backup} disabled={!sel}>
              备份当前配置
            </Button>
          }
        >
          {!sel ? (
            <Empty description="选择左侧设备" />
          ) : (
            <Tabs
              items={[
                {
                  key: "running",
                  label: "运行配置 (Running)",
                  children: <pre className="config-pre">{running}</pre>,
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
                        locale={{ emptyText: <Empty description="暂无快照，点击「备份当前配置」" /> }}
                        columns={[
                          { title: "版本", dataIndex: "version", render: (v) => `v${v}` },
                          {
                            title: "来源", dataIndex: "source",
                            render: (s) => <Tag color={s === "push" ? "green" : "blue"}>{s === "push" ? "开通下发" : s === "backup" ? "手动备份" : s}</Tag>,
                          },
                          { title: "行数", dataIndex: "lines" },
                          { title: "操作人", dataIndex: "created_by" },
                          { title: "备注", dataIndex: "note", ellipsis: true },
                          { title: "时间", dataIndex: "created_at", render: (t) => (t ? dayjs(t).format("MM-DD HH:mm:ss") : "-") },
                          { title: "", render: (_, r) => <a onClick={() => viewSnap(r.id)}>查看</a> },
                        ]}
                      />
                    </>
                  ),
                },
              ]}
            />
          )}
        </Card>
      </Col>
    </Row>
  );
}

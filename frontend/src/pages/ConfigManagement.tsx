import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button, Card, Table, Tag, Tabs, App as AntApp, Empty, Descriptions, Typography, Tooltip, Alert } from "antd";
import { CloudUploadOutlined, DiffOutlined, ReloadOutlined, BookOutlined, SettingOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import { configPreviewModalProps, ConfigPreviewPre } from "../utils/configPreview";
import { usePlatformSettings } from "../hooks/usePlatformSettings";
import { useTc } from "@/i18n/useTc";
import { translateApiText } from "@/i18n/translateApiText";
import { VENDOR_OPTIONS } from "@/constants/formOptions";
import { dataTableProps, TABLE_SCROLL } from "../utils/table";

const VENDOR_COLOR: Record<string, string> = {
  h3c: "blue", huawei: "red", juniper: "green", arista: "orange", cisco: "purple", frr: "cyan",
};

const VENDOR_LABEL: Record<string, string> = {
  h3c: "H3C",
  juniper: "Juniper",
  arista: "Arista",
  cisco: "Cisco",
  frr: "FRR",
};

const SNAPSHOT_SOURCE_LABEL: Record<string, string> = {
  push: "开通下发",
  backup: "手动备份",
  learn: "现网学习",
};

function vendorLabel(vendor: string) {
  return VENDOR_OPTIONS.find((o) => o.value === vendor)?.label ?? VENDOR_LABEL[vendor] ?? vendor;
}

type ConfigDeviceRow = {
  device_id: number;
  name: string;
  vendor: string;
  latest_version?: number;
  learned_version?: number;
  service_count?: number;
};

type AccessBindingRow = {
  interface: string;
  access_mode?: string;
  s_vid?: number | null;
  c_vid?: number | null;
  service_instance?: number;
  vsi_name?: string;
  bridge_domain?: string;
  vni?: number;
  rd?: string;
  rt?: string;
};

function ColoredDiff({ text }: { text: string }) {
  return (
    <pre className="config-pre config-pre-fill">
      {text.split("\n").map((line, i) => (
        <div key={i} style={{
          color: line.startsWith("+") ? "#52c41a" : line.startsWith("-") ? "#ff7875"
            : line.startsWith("@@") ? "#ff8c1a" : undefined,
        }}>{line}</div>
      ))}
    </pre>
  );
}

export default function ConfigManagement() {
  const { tc, isEn } = useTc();
  const { message, modal } = AntApp.useApp();
  const { platform } = usePlatformSettings();
  const [devices, setDevices] = useState<ConfigDeviceRow[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [running, setRunning] = useState<string>("");
  const [snaps, setSnaps] = useState<any[]>([]);
  const [diff, setDiff] = useState<string>("");
  const [drift, setDrift] = useState<string>("");
  const [learned, setLearned] = useState<any>(null);
  const [devicesLoading, setDevicesLoading] = useState(false);

  async function loadDevices() {
    setDevicesLoading(true);
    try {
      const { data } = await api.get("/config/devices");
      setDevices(data);
      if (!sel && data.length) select(data[0].device_id);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("设备列表加载失败"));
    } finally {
      setDevicesLoading(false);
    }
  }
  useEffect(() => { loadDevices(); }, []);

  async function select(id: number) {
    setSel(id);
    try {
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
    } catch (e: any) {
      message.error(e?.response?.data?.detail || tc("设备配置加载失败"));
    }
  }

  async function backup() {
    if (!sel) return;
    const hide = message.loading(tc("正在拉取设备 running-config..."), 0);
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
      message.success(tc('现网配置学习完成'));
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
      <Alert
        className="config-management-alert"
        type="info"
        showIcon
        style={{ marginBottom: 0 }}
        message={
          platform?.auto_learn_enabled !== false
            ? translateApiText(
                `定时自动拉取已开启（间隔 ${platform?.auto_learn_interval_seconds ?? 60} 秒）`,
                tc,
                isEn,
              )
            : tc("定时自动拉取已关闭")
        }
        description={
          <>{tc('可在')}<Link to="/settings/config-learn">{tc('平台设置 → 配置管理')}</Link>{tc('调整自动拉取、变更保护与快照策略。')}</>
        }
        action={
          <Link to="/settings/config-learn">
            <Button size="small" icon={<SettingOutlined />}>{tc('去设置')}</Button>
          </Link>
        }
      />
      <Card
        className="config-panel-card config-management-devices"
        title={tc('设备配置')}
        extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadDevices} />}
      >
        <Table<ConfigDeviceRow>
          {...dataTableProps(TABLE_SCROLL.lg)}
          rowKey="device_id"
          size="small"
          className="config-device-table"
          pagination={false}
          loading={devicesLoading}
          locale={{ emptyText: tc("暂无纳管设备 · 先在「网络设备」中添加") }}
          dataSource={devices}
          tableLayout="fixed"
          onRow={(r) => ({ onClick: () => select(r.device_id), style: { cursor: "pointer" } })}
          rowClassName={(r) => (r.device_id === sel ? "ant-table-row-selected" : "")}
          columns={[
            {
              title: tc('设备'),
              dataIndex: "name",
              width: 220,
              ellipsis: { showTitle: false },
              render: (name: string) => (
                <Tooltip title={name}>
                  <span className="config-device-name">{name}</span>
                </Tooltip>
              ),
            },
            {
              title: tc('厂商'),
              dataIndex: "vendor",
              width: 72,
              align: "center",
              render: (v: string) => (
                <Tag color={VENDOR_COLOR[v]} className="config-inline-tag">
                  {vendorLabel(v)}
                </Tag>
              ),
            },
            {
              title: tc('版本'),
              dataIndex: "latest_version",
              width: 56,
              align: "center",
              render: (v?: number) => (v ? `v${v}` : "—"),
            },
            {
              title: tc('现网学习'),
              dataIndex: "learned_version",
              render: (v?: number, r?: ConfigDeviceRow) =>
                v ? (
                  <Tag color="orange" className="config-inline-tag">
                    v{v} · {r?.service_count ?? 0} {tc("业务")}
                  </Tag>
                ) : (
                  <Tag className="config-inline-tag">{tc('未学习')}</Tag>
                ),
            },
          ]}
        />
      </Card>

      <Card
        className="config-panel-card config-management-detail"
        title={tc('配置管理')}
        extra={
          <Button.Group>
            <Button icon={<BookOutlined />} onClick={runLearn} disabled={!sel}>{tc('现网学习')}</Button>
            <Button type="primary" icon={<CloudUploadOutlined />} onClick={backup} disabled={!sel}>{tc('备份现网配置')}</Button>
          </Button.Group>
        }
      >
        {!sel ? (
          <Empty description={tc('选择左侧设备')} />
        ) : (
          <Tabs
            className="config-tabs"
            items={[
              {
                key: "running",
                label: tc('平台期望配置 (Desired)'),
                children: (
                  <>
                    <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8, fontSize: 12 }}>{tc('由平台纳管专线拼装的目标配置；与设备现网配置可能不同。备份请使用右上角「备份现网配置」。')}</Typography.Text>
                    <pre className="config-pre config-pre-fill">{running}</pre>
                  </>
                ),
              },
              {
                key: "learned",
                label: tc('现网学习'),
                children: learned?.has_learned_config ? (
                  <>
                    <Descriptions size="small" bordered column={2} style={{ marginBottom: 12 }}>
                      <Descriptions.Item label={tc('学习版本')}>v{learned.latest_snapshot_version}</Descriptions.Item>
                      <Descriptions.Item label={tc('学习时间')}>
                        {learned.latest_snapshot_at ? dayjs(learned.latest_snapshot_at).format("YYYY-MM-DD HH:mm:ss") : "-"}
                      </Descriptions.Item>
                      <Descriptions.Item label={tc('业务数')}>
                        {learned.inventory?.service_count ?? 0}
                      </Descriptions.Item>
                      <Descriptions.Item label={tc('接入绑定')}>
                        {learned.inventory?.binding_count ?? learned.inventory?.access_bindings?.length ?? 0}
                      </Descriptions.Item>
                      <Descriptions.Item label={tc('VLAN 数')}>
                        {learned.inventory?.vlan_ids?.length ?? 0}
                      </Descriptions.Item>
                      <Descriptions.Item label={tc('漂移行数')}>{learned.drift_line_count ?? 0}</Descriptions.Item>
                    </Descriptions>
                    {learned.inventory?.l2_services?.length > 0 && (
                      <Table
                        {...dataTableProps(TABLE_SCROLL.md)}
                        size="small"
                        rowKey="name"
                        pagination={false}
                        className="config-service-table"
                        style={{ marginBottom: 12 }}
                        dataSource={learned.inventory.l2_services}
                        tableLayout="fixed"
                        scroll={{ x: 720 }}
                        columns={[
                          { title: tc("业务"), dataIndex: "name", width: 160, ellipsis: true },
                          { title: "VNI", dataIndex: "vni", width: 88 },
                          { title: "RD", dataIndex: "rd", width: 140, ellipsis: true },
                          { title: "RT", dataIndex: "rt", width: 140, ellipsis: true },
                          {
                            title: tc('接口'),
                            dataIndex: "interfaces",
                            width: 180,
                            ellipsis: true,
                            render: (v: string[]) => v?.join(", ") || "—",
                          },
                        ]}
                      />
                    )}
                    {learned.inventory?.access_bindings?.length > 0 && (
                      <Table
                        {...dataTableProps(TABLE_SCROLL.md)}
                        size="small"
                        rowKey={(row: AccessBindingRow) =>
                          `${row.interface}-${row.s_vid ?? "na"}-${row.service_instance ?? row.bridge_domain ?? ""}`
                        }
                        pagination={false}
                        className="config-binding-table"
                        style={{ marginBottom: 12 }}
                        dataSource={learned.inventory.access_bindings as AccessBindingRow[]}
                        tableLayout="fixed"
                        scroll={{ x: 960 }}
                        columns={[
                          { title: "接口", dataIndex: "interface", width: 160, ellipsis: true },
                          { title: tc("模式"), dataIndex: "access_mode", width: 72 },
                          {
                            title: "S-VID",
                            dataIndex: "s_vid",
                            width: 72,
                            render: (v: number | null) => v ?? "—",
                          },
                          {
                            title: "C-VID",
                            dataIndex: "c_vid",
                            width: 72,
                            render: (v: number | null) => v ?? "—",
                          },
                          {
                            title: "SI / BD",
                            width: 120,
                            ellipsis: true,
                            render: (_: unknown, row: AccessBindingRow) =>
                              row.service_instance != null
                                ? `SI ${row.service_instance}`
                                : row.bridge_domain
                                  ? `BD ${row.bridge_domain}`
                                  : row.vsi_name || "—",
                          },
                          { title: "VSI", dataIndex: "vsi_name", width: 140, ellipsis: true, render: (v: string) => v || "—" },
                          { title: "VNI", dataIndex: "vni", width: 88, render: (v: number) => v ?? "—" },
                          { title: "RD", dataIndex: "rd", width: 140, ellipsis: true, render: (v: string) => v || "—" },
                          { title: "RT", dataIndex: "rt", width: 140, ellipsis: true, render: (v: string) => v || "—" },
                        ]}
                      />
                    )}
                    <Button size="small" icon={<DiffOutlined />} onClick={loadDrift}>{tc('平台 vs 现网 配置漂移')}</Button>
                    {drift && <ColoredDiff text={drift} />}
                  </>
                ) : (
                  <Empty description={tc('尚未执行现网学习')}>
                    <Button type="primary" icon={<BookOutlined />} onClick={runLearn}>{tc('立即学习')}</Button>
                  </Empty>
                ),
              },
              {
                key: "history",
                label: `${tc("版本历史")} (${snaps.length})`,
                children: (
                  <>
                    <Button size="small" icon={<DiffOutlined />} onClick={loadDiff} style={{ marginBottom: 8 }}>{tc('对比最近两版')}</Button>
                    {diff && <ColoredDiff text={diff} />}
                    <Table
                      {...dataTableProps(TABLE_SCROLL.lg)}
                      size="small"
                      rowKey="id"
                      className="config-history-table"
                      tableLayout="fixed"
                      scroll={{ y: "calc(100vh - 420px)" }}
                      pagination={{
                        defaultPageSize: 15,
                        showSizeChanger: true,
                        pageSizeOptions: ["10", "15", "20", "50"],
                        showTotal: (total) => `共 ${total} 个版本`,
                      }}
                      dataSource={snaps}
                      locale={{ emptyText: <Empty description={tc('暂无快照，点击「备份现网配置」')} /> }}
                      columns={[
                        { title: "版本", dataIndex: "version", width: 72, render: (v) => `v${v}` },
                        {
                          title: tc('来源'),
                          dataIndex: "source",
                          width: 96,
                          render: (s: string) => (
                            <Tag
                              className="config-inline-tag"
                              color={s === "push" ? "green" : s === "learn" ? "orange" : "blue"}
                            >
                              {tc(SNAPSHOT_SOURCE_LABEL[s] || s)}
                            </Tag>
                          ),
                        },
                        { title: "行数", dataIndex: "lines", width: 72, align: "right" },
                        {
                          title: tc('操作人'),
                          dataIndex: "created_by",
                          width: 88,
                          ellipsis: true,
                          render: (v?: string) => v || "—",
                        },
                        {
                          title: tc('备注'),
                          dataIndex: "note",
                          ellipsis: true,
                          render: (v?: string) => (
                            <Tooltip title={v}>
                              <span className="config-note-cell">{v || "—"}</span>
                            </Tooltip>
                          ),
                        },
                        {
                          title: tc('时间'),
                          dataIndex: "created_at",
                          width: 112,
                          render: (t) => (t ? dayjs(t).format("MM-DD HH:mm") : "—"),
                        },
                        {
                          title: "",
                          width: 56,
                          fixed: "right",
                          render: (_, r) => <a onClick={() => viewSnap(r.id)}>{tc('查看')}</a>,
                        },
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

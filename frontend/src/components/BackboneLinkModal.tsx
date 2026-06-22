import { useEffect, useMemo, useState } from "react";
import {
  App as AntApp,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { BulbOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { Device, LinkPlan, LinkUsage, UplinkCandidate } from "../api/types";
import { usePlatformSettings } from "../hooks/usePlatformSettings";
import InterfaceNameCell from "./InterfaceNameCell";
import { useTc } from "@/i18n/useTc";
import {
  formatInterfaceShort,
  formatInterfaceTooltip,
  formatOperStatus,
  isVlanInterface,
} from "../utils/networkDisplay";
import { fmtLinkBw } from "../utils/linkUtilization";

const LINK_TYPE_LABEL: Record<string, string> = {
  dci: "跨站点 DCI",
  intra_dc: "站内互联",
  access: "接入",
  uplink: "上联",
};

function linkPlanSelectionKey(row: LinkPlan): string {
  return `${row.device_a_id}:${row.device_z_id}:${row.interface_a}:${row.interface_z}`;
}

function clipDescription(desc?: string | null, max = 56) {
  const text = desc?.trim();
  if (!text) return null;
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function portOptionLabel(c: UplinkCandidate) {
  const short = formatInterfaceShort(c.name);
  const desc = clipDescription(c.description);
  if (!desc) return `${short} · ${fmtLinkBw(c.speed_mbps)}`;
  return `${short} — ${desc}`;
}

function PortCandidateOption({ candidate }: { candidate: UplinkCandidate }) {
  const { tc } = useTc();
  const short = formatInterfaceShort(candidate.name);
  const desc = candidate.description?.trim();
  const unavailable = candidate.score <= 0;
  return (
    <div className={`backbone-port-option${unavailable ? " backbone-port-option-muted" : ""}`}>
      <div className="backbone-port-option-name">
        <Tooltip title={short === candidate.name ? undefined : formatInterfaceTooltip(candidate.name)}>
          <InterfaceNameCell name={candidate.name} />
        </Tooltip>
        {unavailable ? <Tag color="default">{tc('不推荐')}</Tag> : null}
      </div>
      {desc ? (
        <div className="backbone-port-option-desc" title={desc}>
          {desc}
        </div>
      ) : null}
      <div className="backbone-port-option-meta">
        {fmtLinkBw(candidate.speed_mbps)}
        {candidate.oper_status ? ` · ${formatOperStatus(candidate.oper_status)}` : ""}
        {candidate.reason ? ` · ${candidate.reason}` : ""}
      </div>
    </div>
  );
}

function EndpointCell({
  device,
  iface,
  description,
}: {
  device: string;
  iface: string;
  description?: string | null;
}) {
  const desc = description?.trim();
  return (
    <div>
      <div>{device}</div>
      <InterfaceNameCell name={iface} />
      {desc ? (
        <Typography.Text type="secondary" style={{ fontSize: 12 }} title={desc}>
          {clipDescription(desc, 48)}
        </Typography.Text>
      ) : null}
    </div>
  );
}

type Props = {
  open: boolean;
  devices: Device[];
  editLink?: LinkUsage | null;
  onClose: () => void;
  onSaved: () => void;
};

export default function BackboneLinkModal({ open, devices, editLink, onClose, onSaved }: Props) {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const { platform } = usePlatformSettings();
  const isEdit = Boolean(editLink);
  const [suggestions, setSuggestions] = useState<LinkPlan[]>([]);
  const [selectedPlans, setSelectedPlans] = useState<LinkPlan[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [saving, setSaving] = useState(false);
  const [manualPlan, setManualPlan] = useState<LinkPlan | null>(null);
  const [candidatesA, setCandidatesA] = useState<UplinkCandidate[]>([]);
  const [candidatesZ, setCandidatesZ] = useState<UplinkCandidate[]>([]);
  const [form] = Form.useForm();

  const deviceOptions = useMemo(
    () =>
      devices.map((d) => ({
        value: d.id,
        label: d.site_id ? `${d.name} (站点 ${d.site_id})` : d.name,
      })),
    [devices],
  );

  const alarmHint =
    platform != null
      ? `留空使用平台默认 ${platform.threshold_link_utilization_pct}%`
      : "留空使用平台默认";

  async function loadSuggestions() {
    setLoadingSuggestions(true);
    try {
      const { data } = await api.get<LinkPlan[]>("/capacity/links/suggestions");
      setSuggestions(data);
      setSelectedPlans(data);
    } finally {
      setLoadingSuggestions(false);
    }
  }

  async function loadCandidates(deviceId: number, side: "a" | "z") {
    const { data } = await api.get<UplinkCandidate[]>(
      `/capacity/devices/${deviceId}/uplink-candidates`,
      { params: { all: true } },
    );
    if (side === "a") setCandidatesA(data);
    else setCandidatesZ(data);
  }

  async function refreshManualPlan(
    deviceAId?: number,
    deviceZId?: number,
    interfaceA?: string,
    interfaceZ?: string,
  ) {
    const aId = deviceAId ?? form.getFieldValue("device_a_id");
    const zId = deviceZId ?? form.getFieldValue("device_z_id");
    if (!aId || !zId || aId === zId) {
      setManualPlan(null);
      return;
    }
    const { data } = await api.get<LinkPlan>("/capacity/links/plan", {
      params: {
        device_a_id: aId,
        device_z_id: zId,
        interface_a: interfaceA,
        interface_z: interfaceZ,
      },
    });
    setManualPlan(data);
    if (!isEdit) {
      form.setFieldsValue({
        name: data.name,
        type: data.type,
        interface_a: data.interface_a,
        interface_z: data.interface_z,
        capacity_mbps: data.capacity_mbps,
      });
    }
  }

  useEffect(() => {
    if (!open) return;

    async function init() {
      if (editLink) {
        form.setFieldsValue({
          device_a_id: editLink.device_a_id,
          device_z_id: editLink.device_z_id,
          interface_a: editLink.interface_a,
          interface_z: editLink.interface_z,
          name: editLink.name,
          type: editLink.type,
          capacity_mbps: editLink.capacity_mbps,
          alarm_utilization_pct: editLink.alarm_utilization_pct,
          supplier: editLink.supplier,
        });
        setManualPlan(null);
        setSuggestions([]);
        setSelectedPlans([]);
        await Promise.all([
          loadCandidates(editLink.device_a_id, "a"),
          loadCandidates(editLink.device_z_id, "z"),
        ]);
        return;
      }

      loadSuggestions();
      form.resetFields();
      setManualPlan(null);
      setCandidatesA([]);
      setCandidatesZ([]);
    }

    void init();
  }, [open, editLink]);

  async function applySuggestions() {
    if (!selectedPlans.length) {
      message.warning(tc('请至少选择一条推荐链路'));
      return;
    }
    setSaving(true);
    try {
      await api.post("/capacity/links/bulk", {
        links: selectedPlans.map((row) => ({
          name: row.name,
          type: row.type,
          device_a_id: row.device_a_id,
          device_z_id: row.device_z_id,
          interface_a: row.interface_a,
          interface_z: row.interface_z,
          capacity_mbps: row.capacity_mbps,
        })),
      });
      message.success(`已创建 ${selectedPlans.length} 条骨干链路`);
      onSaved();
      onClose();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    } finally {
      setSaving(false);
    }
  }

  async function createManual() {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.post("/capacity/links", values);
      message.success(tc('骨干链路已创建'));
      onSaved();
      onClose();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    } finally {
      setSaving(false);
    }
  }

  async function saveEdit() {
    if (!editLink) return;
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.patch(`/capacity/links/${editLink.link_id}`, values);
      message.success(tc('骨干链路已更新'));
      onSaved();
      onClose();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "更新失败");
    } finally {
      setSaving(false);
    }
  }

  const vlanHintA = candidatesA.length > 0 && !candidatesA.some((c) => isVlanInterface(c.name));
  const vlanHintZ = candidatesZ.length > 0 && !candidatesZ.some((c) => isVlanInterface(c.name));

  return (
    <Drawer
      title={isEdit ? "编辑骨干链路" : "配置骨干链路"}
      width="min(96vw, 1080px)"
      open={open}
      onClose={onClose}
      destroyOnClose
      extra={
        isEdit ? null : (
          <Space>
            <Button onClick={loadSuggestions} loading={loadingSuggestions}>{tc('刷新推荐')}</Button>
            <Button
              type="primary"
              loading={saving}
              disabled={!selectedPlans.length}
              onClick={applySuggestions}
            >
              应用选中推荐 ({selectedPlans.length})
            </Button>
          </Space>
        )
      }
    >
      <Typography.Paragraph type="secondary">{tc('骨干 / DCI 推荐需同时满足：相同 VLAN、OSPF 100、/30 互联地址成对。手动选配仍可选其他端口。请确保已 SNMP 发现或现网学习。')}</Typography.Paragraph>

      {!isEdit ? (
        <Table<LinkPlan>
          size="small"
          className="data-table"
          rowKey={linkPlanSelectionKey}
          loading={loadingSuggestions}
          dataSource={suggestions}
          pagination={false}
          rowSelection={{
            selectedRowKeys: selectedPlans.map(linkPlanSelectionKey),
            onChange: (_keys, rows) => setSelectedPlans(rows),
          }}
          style={{ marginBottom: 24 }}
          locale={{ emptyText: "暂无推荐 · 请确认设备已 SNMP 发现且跨站点存在未建链路" }}
          columns={[
            {
              title: tc('链路'),
              dataIndex: "name",
              width: 160,
              ellipsis: true,
            },
            {
              title: tc('类型'),
              dataIndex: "type",
              width: 100,
              render: (t: string) => (
                <Tag color={t === "dci" ? "blue" : "green"}>{LINK_TYPE_LABEL[t] || t}</Tag>
              ),
            },
            {
              title: tc('A 端'),
              width: 200,
              render: (_: unknown, row) => (
                <EndpointCell
                  device={row.device_a}
                  iface={row.interface_a}
                  description={row.interface_a_description}
                />
              ),
            },
            {
              title: tc('Z 端'),
              width: 200,
              render: (_: unknown, row) => (
                <EndpointCell
                  device={row.device_z}
                  iface={row.interface_z}
                  description={row.interface_z_description}
                />
              ),
            },
            {
              title: tc('带宽'),
              dataIndex: "capacity_mbps",
              width: 90,
              render: (v: number) => fmtLinkBw(v),
            },
            {
              title: tc('评分'),
              dataIndex: "score",
              width: 72,
              render: (v: number) => <Tag color={v >= 80 ? "green" : "gold"}>{v}</Tag>,
            },
            {
              title: tc('依据'),
              dataIndex: "reason",
              ellipsis: true,
            },
          ]}
        />
      ) : null}

      <Typography.Title level={5}>
        <BulbOutlined /> {isEdit ? "链路配置" : "手动选配"}
      </Typography.Title>
      <Form form={form} layout="vertical" onFinish={isEdit ? saveEdit : createManual}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Form.Item
            name="device_a_id"
            label={tc('A 端设备')}
            rules={[{ required: true, message: "请选择 A 端设备" }]}
          >
            <Select
              showSearch
              optionFilterProp="label"
              options={deviceOptions}
              placeholder={tc('选择设备')}
              onChange={async (id) => {
                await loadCandidates(id, "a");
                const zId = form.getFieldValue("device_z_id");
                if (zId) await refreshManualPlan(id, zId);
              }}
            />
          </Form.Item>
          <Form.Item
            name="device_z_id"
            label={tc('Z 端设备')}
            rules={[{ required: true, message: "请选择 Z 端设备" }]}
          >
            <Select
              showSearch
              optionFilterProp="label"
              options={deviceOptions}
              placeholder={tc('选择设备')}
              onChange={async (id) => {
                await loadCandidates(id, "z");
                const aId = form.getFieldValue("device_a_id");
                if (aId) await refreshManualPlan(aId, id);
              }}
            />
          </Form.Item>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Form.Item
            name="interface_a"
            label={`A 端端口${candidatesA.length ? ` (${candidatesA.length})` : ""}`}
            extra={
              vlanHintA
                ? "未发现 Vlanif / Vlan-interface，请在设备页执行 SNMP 发现或现网学习后刷新"
                : "展示设备全部已发现接口，含端口描述；评分高的排在前面"
            }
          >
            <Select
              showSearch
              placeholder={tc('选择接口')}
              optionFilterProp="label"
              popupMatchSelectWidth={false}
              styles={{ popup: { root: { minWidth: 420 } } }}
              listHeight={400}
              options={candidatesA.map((c) => ({
                value: c.name,
                label: portOptionLabel(c),
                candidate: c,
              }))}
              optionRender={(opt) => (
                <PortCandidateOption candidate={(opt.data as { candidate: UplinkCandidate }).candidate} />
              )}
              onChange={(name) => {
                const aId = form.getFieldValue("device_a_id");
                const zId = form.getFieldValue("device_z_id");
                if (aId && zId) refreshManualPlan(aId, zId, name, form.getFieldValue("interface_z"));
              }}
            />
          </Form.Item>
          <Form.Item
            name="interface_z"
            label={`Z 端端口${candidatesZ.length ? ` (${candidatesZ.length})` : ""}`}
            extra={
              vlanHintZ
                ? "未发现 Vlanif / Vlan-interface，请在设备页执行 SNMP 发现或现网学习后刷新"
                : "展示设备全部已发现接口，含端口描述；评分高的排在前面"
            }
          >
            <Select
              showSearch
              placeholder={tc('选择接口')}
              optionFilterProp="label"
              popupMatchSelectWidth={false}
              styles={{ popup: { root: { minWidth: 420 } } }}
              listHeight={400}
              options={candidatesZ.map((c) => ({
                value: c.name,
                label: portOptionLabel(c),
                candidate: c,
              }))}
              optionRender={(opt) => (
                <PortCandidateOption candidate={(opt.data as { candidate: UplinkCandidate }).candidate} />
              )}
              onChange={(name) => {
                const aId = form.getFieldValue("device_a_id");
                const zId = form.getFieldValue("device_z_id");
                if (aId && zId) refreshManualPlan(aId, zId, form.getFieldValue("interface_a"), name);
              }}
            />
          </Form.Item>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 16 }}>
          <Form.Item name="name" label={tc('链路名称')} rules={[{ required: true }]}>
            <Input placeholder={tc('自动生成')} />
          </Form.Item>
          <Form.Item name="type" label={tc('类型')} rules={[{ required: true }]}>
            <Select
              options={[
                { value: "dci", label: LINK_TYPE_LABEL.dci },
                { value: "intra_dc", label: LINK_TYPE_LABEL.intra_dc },
              ]}
            />
          </Form.Item>
          <Form.Item name="capacity_mbps" label={tc('合同带宽 (Mbps)')} rules={[{ required: true }]}>
            <Input type="number" min={1} />
          </Form.Item>
        </div>

        <Form.Item name="supplier" label={tc('供应商')} extra={tc('运营商 / 传输供应商，便于按供应商筛选利用率')}>
          <Input placeholder={tc('例如 中国电信、Cogent、Equinix')} allowClear />
        </Form.Item>

        <Form.Item name="alarm_utilization_pct" label={tc('利用率告警阈值 (%)')} extra={alarmHint}>
          <InputNumber min={0} max={100} style={{ width: "100%" }} placeholder={tc('平台默认')} />
        </Form.Item>

        {manualPlan ? (
          <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
            推荐评分 {manualPlan.score} · {manualPlan.reason}
          </Typography.Text>
        ) : null}

        <Button
          type="primary"
          htmlType="submit"
          icon={isEdit ? <EditOutlined /> : <PlusOutlined />}
          loading={saving}
        >
          {isEdit ? "保存修改" : "创建此链路"}
        </Button>
      </Form>
    </Drawer>
  );
}

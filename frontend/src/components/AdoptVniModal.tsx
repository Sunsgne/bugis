import {
  Alert,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Spin,
  Table,
  Tag,
  Typography,
  App as AntApp,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Circuit, Paginated, Tenant } from "../api/types";
import { formatVlanLabel } from "../utils/networkDisplay";
import { useTc } from "@/i18n/useTc";

export type CircuitAdoptVniPreview = {
  vni: number;
  vsi_name?: string | null;
  rd?: string | null;
  rt?: string | null;
  endpoints: Array<{
    key: string;
    device_id: number;
    device_name: string;
    interface_name: string;
    access_mode: string;
    vlan_id?: number | null;
    inner_vlan_id?: number | null;
    vni: number;
    vsi_name?: string | null;
    description?: string | null;
    adoptable: boolean;
    reason?: string | null;
  }>;
  adoptable_count: number;
  total_count: number;
  existing_circuit_id?: number | null;
  existing_circuit_code?: string | null;
  conflict_message?: string | null;
  can_adopt: boolean;
};

type Props = {
  open: boolean;
  initialVni?: number;
  onClose: () => void;
  onSuccess: (circuit: Circuit) => void;
};

export default function AdoptVniModal({ open, initialVni, onClose, onSuccess }: Props) {
  const { tc } = useTc();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const [tenantOptions, setTenantOptions] = useState<{ value: number; label: string }[]>([]);
  const [tenantsLoading, setTenantsLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [preview, setPreview] = useState<CircuitAdoptVniPreview | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);

  const searchTenants = useCallback(async (q?: string) => {
    setTenantsLoading(true);
    try {
      const { data } = await api.get<Paginated<Tenant>>("/tenants", {
        params: { q: q?.trim() || undefined, page: 1, page_size: 50 },
      });
      setTenantOptions(
        data.items.map((t) => ({ value: t.id, label: `${t.name} (${t.code})` })),
      );
    } finally {
      setTenantsLoading(false);
    }
  }, []);

  const tenantSearchTimer = useMemo(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    return (q: string) => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => void searchTenants(q), 250);
    };
  }, [searchTenants]);

  const loadPreview = useCallback(async (vni: number) => {
    setPreviewLoading(true);
    try {
      const { data } = await api.get<CircuitAdoptVniPreview>("/circuits/adopt-by-vni/preview", {
        params: { vni, refresh_inventory: true },
      });
      setPreview(data);
      const adoptableKeys = data.endpoints.filter((ep) => ep.adoptable).map((ep) => ep.key);
      setSelectedKeys(adoptableKeys);
      if (!form.getFieldValue("name")) {
        form.setFieldsValue({
          name: data.vsi_name || `VNI-${data.vni}`,
        });
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || tc("预览失败"));
      setPreview(null);
      setSelectedKeys([]);
    } finally {
      setPreviewLoading(false);
    }
  }, [form, message, tc]);

  useEffect(() => {
    if (!open) return;
    void searchTenants("");
    form.resetFields();
    setPreview(null);
    setSelectedKeys([]);
    if (initialVni != null) {
      form.setFieldsValue({ vni: initialVni });
      void loadPreview(initialVni);
    }
  }, [open, initialVni, form, searchTenants, loadPreview]);

  async function submit() {
    const values = await form.validateFields();
    if (!preview?.can_adopt || selectedKeys.length === 0) {
      message.warning(tc("请选择可纳管的接入端点"));
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post<Circuit>("/circuits/adopt-from-vni", {
        name: values.name,
        tenant_id: values.tenant_id,
        vni: values.vni,
        bandwidth_mbps: values.bandwidth_mbps,
        description: values.description || "现网纳管（按 VNI · 不下发配置）",
        endpoint_keys: selectedKeys,
        refresh_inventory: false,
      });
      onSuccess(data);
      onClose();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || tc("纳管失败"));
    } finally {
      setLoading(false);
    }
  }

  const adoptableSelected = preview?.endpoints.filter(
    (ep) => ep.adoptable && selectedKeys.includes(ep.key),
  ).length ?? 0;

  return (
    <Modal
      title={tc("按 VNI 纳管现网专线")}
      open={open}
      onCancel={onClose}
      onOk={submit}
      confirmLoading={loading}
      okText={tc("纳管到平台")}
      okButtonProps={{
        disabled: !preview?.can_adopt || adoptableSelected === 0,
      }}
      width={860}
      destroyOnClose
      maskClosable={!loading}
    >
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        {tc("输入 VNI 后，平台将从整网现网学习结果中自动发现关联的设备与接入接口。")}
        <Typography.Text strong>{tc("不会向设备下发任何配置")}</Typography.Text>
        {tc("，现网流量不受影响。")}
      </Typography.Paragraph>

      <Form form={form} layout="vertical" className="app-form">
        <Form.Item
          name="vni"
          label="VNI"
          rules={[{ required: true, message: tc("请输入 VNI") }]}
        >
          <InputNumber
            min={1}
            max={16777215}
            style={{ width: "100%" }}
            placeholder={tc("例如 10100")}
            onBlur={() => {
              const vni = form.getFieldValue("vni");
              if (vni != null) void loadPreview(Number(vni));
            }}
            onPressEnter={() => {
              const vni = form.getFieldValue("vni");
              if (vni != null) void loadPreview(Number(vni));
            }}
          />
        </Form.Item>
        <Form.Item name="name" label={tc("业务名称")} rules={[{ required: true, message: tc("请输入名称") }]}>
          <Input placeholder={tc("专线名称")} />
        </Form.Item>
        <Form.Item name="tenant_id" label={tc("客户")} rules={[{ required: true, message: tc("请选择客户") }]}>
          <Select
            showSearch
            filterOption={false}
            loading={tenantsLoading}
            onSearch={tenantSearchTimer}
            options={tenantOptions}
            placeholder={tc("搜索客户名称或编码")}
          />
        </Form.Item>
        <Form.Item name="bandwidth_mbps" label={tc("带宽 (Mbps)")} initialValue={100}>
          <InputNumber min={1} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="description" label={tc("备注")}>
          <Input.TextArea rows={2} placeholder={tc("可选")} />
        </Form.Item>
      </Form>

      {previewLoading ? (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin tip={tc("正在扫描整网接入绑定…")} />
        </div>
      ) : preview ? (
        <>
          {preview.conflict_message ? (
            <Alert type="error" showIcon message={preview.conflict_message} style={{ marginBottom: 12 }} />
          ) : null}
          {preview.total_count === 0 ? (
            <Alert
              type="warning"
              showIcon
              message={tc("未发现该 VNI 的接入绑定")}
              description={tc("请确认设备已完成现网学习，且 running-config 中存在对应 VSI/BD 与 AC 绑定。")}
            />
          ) : (
            <>
              <Typography.Paragraph style={{ marginBottom: 8 }}>
                VNI {preview.vni}
                {preview.vsi_name ? ` · ${preview.vsi_name}` : ""}
                {preview.rd ? ` · RD ${preview.rd}` : ""}
                {" · "}
                {tc("已发现")} {preview.total_count} {tc("个端点")}
                {preview.adoptable_count < preview.total_count
                  ? `（${preview.adoptable_count} ${tc("可纳管")}）`
                  : ""}
              </Typography.Paragraph>
              <Table
                size="small"
                rowKey="key"
                pagination={false}
                scroll={{ y: 240 }}
                dataSource={preview.endpoints}
                rowSelection={{
                  selectedRowKeys: selectedKeys,
                  onChange: (keys) => setSelectedKeys(keys as string[]),
                  getCheckboxProps: (row) => ({ disabled: !row.adoptable }),
                }}
                columns={[
                  { title: tc("设备"), dataIndex: "device_name", width: 140, ellipsis: true },
                  { title: tc("接口"), dataIndex: "interface_name", width: 120 },
                  {
                    title: tc("封装 / VLAN"),
                    width: 140,
                    render: (_: unknown, row) =>
                      formatVlanLabel(row.access_mode, row.vlan_id, row.inner_vlan_id),
                  },
                  {
                    title: tc("状态"),
                    width: 120,
                    render: (_: unknown, row) =>
                      row.adoptable ? (
                        <Tag color="green">{tc("可纳管")}</Tag>
                      ) : (
                        <Tag color="default">{row.reason || tc("不可纳管")}</Tag>
                      ),
                  },
                ]}
              />
            </>
          )}
        </>
      ) : null}
    </Modal>
  );
}

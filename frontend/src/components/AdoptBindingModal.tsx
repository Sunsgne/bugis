import { Form, Input, InputNumber, Modal, Select, Typography, App as AntApp } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Circuit, DevicePortBinding, Paginated, Tenant } from "../api/types";
import { formatVlanLabel } from "../utils/networkDisplay";

type Props = {
  open: boolean;
  binding: DevicePortBinding | null;
  deviceId: number;
  onClose: () => void;
  onSuccess: (circuit: Circuit) => void;
};

export default function AdoptBindingModal({
  open,
  binding,
  deviceId,
  onClose,
  onSuccess,
}: Props) {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const [tenantOptions, setTenantOptions] = useState<{ value: number; label: string }[]>([]);
  const [tenantsLoading, setTenantsLoading] = useState(false);
  const [loading, setLoading] = useState(false);

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

  useEffect(() => {
    if (!open) return;
    void searchTenants("");
    form.setFieldsValue({
      name: binding?.business_name || binding?.vsi_name || binding?.description || "",
      tenant_id: binding?.tenant_id ?? undefined,
      bandwidth_mbps: binding?.bandwidth_mbps ?? binding?.rate_limit_mbps ?? 100,
    });
  }, [open, binding, form, searchTenants]);

  useEffect(() => {
    if (!open || !binding?.tenant_id) return;
    const preset = tenantOptions.find((o) => o.value === binding.tenant_id);
    if (preset) return;
    void (async () => {
      try {
        const { data } = await api.get<Tenant>(`/tenants/${binding.tenant_id}`);
        setTenantOptions((prev) => {
          if (prev.some((o) => o.value === data.id)) return prev;
          return [{ value: data.id, label: `${data.name} (${data.code})` }, ...prev];
        });
      } catch {
        // optional preset from binding row
      }
    })();
  }, [open, binding?.tenant_id, tenantOptions]);

  async function submit() {
    if (!binding) return;
    const values = await form.validateFields();
    setLoading(true);
    try {
      const { data } = await api.post<Circuit>("/circuits/adopt-from-inventory", {
        name: values.name,
        tenant_id: values.tenant_id,
        bandwidth_mbps: values.bandwidth_mbps,
        description: values.description || "现网纳管（不下发配置）",
        refresh_inventory: false,
        bindings: [
          {
            device_id: deviceId,
            label: "A",
            interface_name: binding.interface_name,
            access_mode: binding.access_mode || "dot1q",
            vlan_id: binding.s_vid,
            inner_vlan_id: binding.c_vid,
          },
        ],
      });
      onSuccess(data);
      onClose();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err?.response?.data?.detail || "纳管失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal
      title="纳管现网业务"
      open={open}
      onCancel={onClose}
      onOk={submit}
      confirmLoading={loading}
      okText="纳管到平台"
      destroyOnClose
      maskClosable={!loading}
    >
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        将设备上已运行的 S-VID 业务登记到平台，<Typography.Text strong>不会向设备下发任何配置</Typography.Text>
        ，现网流量不受影响。建议开启「定时现网自学习」以持续同步线下变更。
      </Typography.Paragraph>
      {binding ? (
        <Typography.Paragraph style={{ marginBottom: 16 }}>
          接口 {binding.interface_name} ·{" "}
          {formatVlanLabel(binding.access_mode, binding.s_vid, binding.c_vid)}
          {binding.vni != null ? ` · VNI ${binding.vni}` : ""}
          {binding.vsi_name ? ` · ${binding.vsi_name}` : ""}
        </Typography.Paragraph>
      ) : null}
      <Form form={form} layout="vertical" className="app-form">
        <Form.Item name="name" label="业务名称" rules={[{ required: true, message: "请输入名称" }]}>
          <Input placeholder="专线名称" />
        </Form.Item>
        <Form.Item name="tenant_id" label="客户" rules={[{ required: true, message: "请选择客户" }]}>
          <Select
            showSearch
            filterOption={false}
            loading={tenantsLoading}
            onSearch={tenantSearchTimer}
            options={tenantOptions}
            placeholder="搜索客户名称或编码"
          />
        </Form.Item>
        <Form.Item name="bandwidth_mbps" label="带宽 (Mbps)">
          <InputNumber min={1} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="description" label="备注">
          <Input.TextArea rows={2} placeholder="可选" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

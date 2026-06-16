import { Form, Input, InputNumber, Modal, Select, Typography } from "antd";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Circuit, DevicePortBinding, Tenant } from "../api/types";
import { fetchAllPages } from "../utils/pagination";
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
  const [form] = Form.useForm();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    fetchAllPages<Tenant>("/tenants").then(setTenants);
    form.setFieldsValue({
      name: binding?.business_name || binding?.vsi_name || binding?.description || "",
      tenant_id: binding?.tenant_id ?? undefined,
      bandwidth_mbps: binding?.bandwidth_mbps ?? binding?.rate_limit_mbps ?? 100,
    });
  }, [open, binding, form]);

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
            optionFilterProp="label"
            options={tenants.map((t) => ({ value: t.id, label: `${t.name} (${t.code})` }))}
            placeholder="选择租户"
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

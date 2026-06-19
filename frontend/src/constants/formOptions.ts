import i18n from "../i18n";
import { tcStatic } from "../i18n/useTc";

function tc(s: string): string {
  return tcStatic(s, i18n.language);
}

function tKey(key: string, zh: string): string {
  return i18n.t(key, { defaultValue: zh });
}

export const VENDOR_OPTIONS = [
  { value: "h3c", get label() { return tKey("form.vendor.h3c", tc("H3C 新华三")); } },
  { value: "huawei", get label() { return tKey("form.vendor.huawei", tc("Huawei 华为")); } },
  { value: "juniper", get label() { return tKey("form.vendor.juniper", tc("Juniper 瞻博")); } },
  { value: "arista", get label() { return "Arista"; } },
  { value: "cisco", get label() { return tKey("form.vendor.cisco", tc("Cisco 思科")); } },
  { value: "frr", get label() { return tKey("form.vendor.frr", tc("FRR 开源路由")); } },
];

export const DEVICE_ROLE_OPTIONS = [
  { value: "spine", get label() { return tKey("form.deviceRole.spine", tc("Spine 核心")); } },
  { value: "leaf", get label() { return tKey("form.deviceRole.leaf", tc("Leaf 接入")); } },
  { value: "border_leaf", get label() { return tKey("form.deviceRole.border_leaf", tc("Border Leaf 边界")); } },
  { value: "vtep", get label() { return tKey("form.deviceRole.vtep", tc("VTEP 隧道端点")); } },
  { value: "pe", get label() { return tKey("form.deviceRole.pe", tc("PE 提供商边缘")); } },
  { value: "p", get label() { return tKey("form.deviceRole.p", tc("P 核心路由器")); } },
  { value: "rr", get label() { return tKey("form.deviceRole.rr", tc("RR 路由反射器")); } },
  { value: "dci_gw", get label() { return tKey("form.deviceRole.dci_gw", tc("DCI Gateway 互联网关")); } },
  { value: "cpe", get label() { return tKey("form.deviceRole.cpe", tc("CPE 客户设备")); } },
];

export const OVERLAY_OPTIONS = [
  { value: "vxlan_evpn", label: "VXLAN-EVPN" },
  { value: "srmpls_evpn", label: "SR-MPLS EVPN" },
];

export const SNMP_VERSION_OPTIONS = [
  { value: "2c", label: "SNMPv2c" },
  { value: "3", label: "SNMPv3" },
];

export const MANAGEMENT_TRANSPORT_OPTIONS = [
  { value: "auto", get label() { return tKey("form.managementTransport.auto", tc("自动（按厂商默认）")); } },
  { value: "netconf", label: "NETCONF" },
  { value: "ssh", label: "SSH CLI" },
];

/** Canonical values stored in API/DB (Chinese literals). */
export const MGMT_IP_TYPE_MANAGEMENT = "管理网";
export const MGMT_IP_TYPE_PUBLIC = "公网";

export const MGMT_IP_TYPE_OPTIONS = [
  { value: MGMT_IP_TYPE_MANAGEMENT, get label() { return tKey("form.mgmtIpType.management", tc("管理网")); } },
  { value: MGMT_IP_TYPE_PUBLIC, get label() { return tKey("form.mgmtIpType.public", tc("公网")); } },
];

export function mgmtIpTypeLabel(value?: string | null): string {
  if (!value || value === MGMT_IP_TYPE_MANAGEMENT) {
    return tKey("form.mgmtIpType.management", tc("管理网"));
  }
  if (value === MGMT_IP_TYPE_PUBLIC) {
    return tKey("form.mgmtIpType.public", tc("公网"));
  }
  return value;
}

export const SNMP_V3_SECURITY_OPTIONS = [
  { value: "noAuthNoPriv", label: "noAuthNoPriv" },
  { value: "authNoPriv", label: "authNoPriv" },
  { value: "authPriv", label: "authPriv" },
];

export function labelForOption(
  options: readonly { value: string; label: string }[],
  value: string | undefined | null,
): string {
  if (!value) return tc("—");
  return options.find((o) => o.value === value)?.label ?? value;
}

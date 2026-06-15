/** Shared select options with full readable labels (dropdown uses popupMatchSelectWidth=false globally). */

export const VENDOR_OPTIONS = [
  { value: "h3c", label: "H3C 新华三" },
  { value: "huawei", label: "Huawei 华为" },
  { value: "juniper", label: "Juniper 瞻博" },
  { value: "arista", label: "Arista" },
  { value: "cisco", label: "Cisco 思科" },
  { value: "frr", label: "FRR 开源路由" },
];

export const DEVICE_ROLE_OPTIONS = [
  { value: "spine", label: "Spine 核心" },
  { value: "leaf", label: "Leaf 接入" },
  { value: "border_leaf", label: "Border Leaf 边界" },
  { value: "vtep", label: "VTEP 隧道端点" },
  { value: "pe", label: "PE 提供商边缘" },
  { value: "p", label: "P 核心路由器" },
  { value: "rr", label: "RR 路由反射器" },
  { value: "dci_gw", label: "DCI Gateway 互联网关" },
  { value: "cpe", label: "CPE 客户设备" },
];

export const OVERLAY_OPTIONS = [
  { value: "vxlan_evpn", label: "VXLAN-EVPN" },
  { value: "srmpls_evpn", label: "SR-MPLS EVPN" },
];

export const SNMP_VERSION_OPTIONS = [
  { value: "2c", label: "SNMPv2c" },
  { value: "3", label: "SNMPv3" },
];

export function labelForOption(
  options: readonly { value: string; label: string }[],
  value: string | undefined | null,
): string {
  if (!value) return "—";
  return options.find((o) => o.value === value)?.label ?? value;
}

import type { TFunction } from "i18next";

/** Status / enum color maps (locale-independent). */
export const STATUS_COLORS = {
  circuit: {
    draft: "default", pending: "gold", provisioning: "processing", active: "green",
    degraded: "orange", suspended: "volcano", decommissioned: "default", failed: "red",
  },
  workOrder: {
    draft: "default", submitted: "blue", approved: "cyan", rejected: "red",
    scheduled: "geekblue", running: "processing", completed: "green", failed: "red", cancelled: "default",
  },
  tenant: { active: "green", suspended: "volcano", terminated: "default" },
  alarmSeverity: {
    critical: "red", major: "volcano", minor: "orange", warning: "gold", info: "blue",
  },
  alarm: { active: "red", acknowledged: "gold", cleared: "green" },
} as const;

export function statusMeta(
  t: TFunction,
  ns: string,
  value: string | undefined | null,
  colorMap: Record<string, string>,
): { label: string; color: string } {
  if (!value) return { label: t("common.dash"), color: "default" };
  const key = `${ns}.${value}`;
  const label = t(key, { defaultValue: value });
  return { label, color: colorMap[value] || "default" };
}

export function circuitStatusMeta(t: TFunction, value?: string | null) {
  return statusMeta(t, "status.circuit", value, STATUS_COLORS.circuit);
}

export function workOrderStatusMeta(t: TFunction, value?: string | null) {
  return statusMeta(t, "status.workOrder", value, STATUS_COLORS.workOrder);
}

export function tenantStatusMeta(t: TFunction, value?: string | null) {
  return statusMeta(t, "status.tenant", value, STATUS_COLORS.tenant);
}

export function alarmSeverityMeta(t: TFunction, value?: string | null) {
  return statusMeta(t, "status.alarmSeverity", value, STATUS_COLORS.alarmSeverity);
}

export function alarmStatusMeta(t: TFunction, value?: string | null) {
  return statusMeta(t, "status.alarm", value, STATUS_COLORS.alarm);
}

export function alarmKindLabel(t: TFunction, value?: string | null): string {
  if (!value) return t("common.dash");
  return t(`status.alarmKind.${value}`, { defaultValue: value });
}

export function serviceTypeLabel(t: TFunction, value?: string | null): string {
  if (!value) return t("common.dash");
  return t(`status.serviceType.${value}`, { defaultValue: value });
}

export function deviceStatusLabel(t: TFunction, value?: string | null): string {
  if (!value) return t("common.dash");
  return t(`status.device.${value}`, { defaultValue: value });
}

export function portStatusLabel(t: TFunction, value?: string | null): string {
  if (!value) return t("common.dash");
  return t(`status.port.${value.toLowerCase()}`, { defaultValue: value });
}

export function accessModeLabel(t: TFunction, mode?: string | null): string {
  if (!mode) return t("common.dash");
  return t(`status.accessMode.${mode}`, { defaultValue: mode });
}

export function discoveredViaLabel(t: TFunction, via?: string | null): string {
  if (!via) return t("common.dash");
  return t(`status.discoveredVia.${via}`, { defaultValue: via });
}

export function vendorOptions(t: TFunction) {
  return (["h3c", "huawei", "juniper", "arista", "cisco", "frr"] as const).map((value) => ({
    value,
    label: t(`form.vendor.${value}`),
  }));
}

export function deviceRoleOptions(t: TFunction) {
  return (
    ["spine", "leaf", "border_leaf", "vtep", "pe", "p", "rr", "dci_gw", "cpe"] as const
  ).map((value) => ({ value, label: t(`form.deviceRole.${value}`) }));
}

export function overlayOptions() {
  return [
    { value: "vxlan_evpn", label: "VXLAN-EVPN" },
    { value: "srmpls_evpn", label: "SR-MPLS EVPN" },
  ];
}

export function snmpVersionOptions() {
  return [
    { value: "2c", label: "SNMPv2c" },
    { value: "3", label: "SNMPv3" },
  ];
}

export function managementTransportOptions(t: TFunction) {
  return (["auto", "netconf", "ssh"] as const).map((value) => ({
    value,
    label: t(`form.managementTransport.${value}`),
  }));
}

export function snmpV3SecurityOptions() {
  return [
    { value: "noAuthNoPriv", label: "noAuthNoPriv" },
    { value: "authNoPriv", label: "authNoPriv" },
    { value: "authPriv", label: "authPriv" },
  ];
}

export function labelForOption(
  options: readonly { value: string; label: string }[],
  value: string | undefined | null,
  t: TFunction,
): string {
  if (!value) return t("common.dash");
  return options.find((o) => o.value === value)?.label ?? value;
}

export function pageRangeLabel(t: TFunction, total: number, page: number, pageSize: number): string {
  if (total === 0) return t("table.noData");
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return t("table.range", {
    start: start.toLocaleString(),
    end: end.toLocaleString(),
    total: total.toLocaleString(),
  });
}

export function tablePaginationTotal(
  t: TFunction,
  total: number,
  range: [number, number] | undefined,
): string {
  if (range) {
    return t("table.range", {
      start: range[0].toLocaleString(),
      end: range[1].toLocaleString(),
      total: total.toLocaleString(),
    });
  }
  return t("table.totalOnly", { total: total.toLocaleString() });
}

export function pageSizeSelectOptions(t: TFunction, sizes: readonly number[]) {
  return sizes.map((n) => ({
    value: n,
    label: t("table.pageSize", { n }),
  }));
}

export function tenantTypeLabel(t: TFunction, value?: string | null): string {
  if (!value) return t("common.dash");
  return t(`status.tenantType.${value}`, { defaultValue: value });
}

export function workOrderTypeLabel(t: TFunction, value?: string | null): string {
  if (!value) return t("common.dash");
  return t(`status.workOrderType.${value}`, { defaultValue: value });
}

export function overlaySourceLabel(t: TFunction, value?: string | null): string {
  if (!value) return t("common.dash");
  return t(`status.overlaySource.${value}`, { defaultValue: value });
}

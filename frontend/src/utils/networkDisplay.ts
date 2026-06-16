/** Compact Chinese-friendly labels for network interface names and port metadata. */

const PORT_SUFFIX = /(\d+(?:\/\d+)+)\s*$/;

const PREFIX_SPEED: Array<[RegExp, string]> = [
  [/^Twenty-FiveGigE/i, "25G"],
  [/^Twenty-FiveGigabitEthernet/i, "25G"],
  [/^HundredGigE/i, "100G"],
  [/^FortyGigE/i, "40G"],
  [/^Ten-GigabitEthernet/i, "10G"],
  [/^TenGigabitEthernet/i, "10G"],
  [/^TenGigE/i, "10G"],
  [/^25GE/i, "25G"],
  [/^100GE/i, "100G"],
  [/^10GE/i, "10G"],
  [/^40GE/i, "40G"],
  [/^GigabitEthernet/i, "千兆"],
  [/^GE/i, "GE"],
  [/^xe-/i, "10G"],
  [/^et-/i, "100G"],
  [/^ge-/i, "GE"],
];

export function interfacePortSuffix(name: string): string | null {
  const match = name.trim().match(PORT_SUFFIX);
  return match ? match[1] : null;
}

/** Huawei L2 sub-interface e.g. 10GE1/0/2.1050 → parent 10GE1/0/2, vlan 1050 */
export function parseHuaweiSubinterface(name: string): { parent: string; vlan: number } | null {
  const trimmed = name.trim();
  const match = trimmed.match(/^(.+)\.(\d+)$/);
  if (!match) return null;
  const parent = match[1];
  if (!interfacePortSuffix(parent) && !/\d+\/\d+/.test(parent)) return null;
  return { parent, vlan: Number(match[2]) };
}

export function isHuaweiSubinterface(name: string): boolean {
  return parseHuaweiSubinterface(name) !== null;
}

export function huaweiPhysicalPort(name: string): string {
  return parseHuaweiSubinterface(name)?.parent ?? name.trim();
}

/** Short display label, e.g. Twenty-FiveGigE1/0/1 → 25G·1/0/1 */
export function formatInterfaceShort(name: string): string {
  const trimmed = name.trim();
  const suffix = interfacePortSuffix(trimmed);
  if (!suffix) return trimmed;

  for (const [pattern, label] of PREFIX_SPEED) {
    if (pattern.test(trimmed)) {
      return `${label}·${suffix}`;
    }
  }
  return suffix.length + 3 < trimmed.length ? suffix : trimmed;
}

export function formatInterfaceTooltip(name: string): string {
  const short = formatInterfaceShort(name);
  return short === name ? name : `接口全名：${name}`;
}

const OPER_STATUS_LABEL: Record<string, string> = {
  up: "在线",
  down: "离线",
  unknown: "未知",
};

export function formatOperStatus(status?: string | null): string {
  if (!status) return "—";
  return OPER_STATUS_LABEL[status.toLowerCase()] || status;
}

const DISCOVERED_VIA_LABEL: Record<string, string> = {
  snmp: "SNMP",
  "snmp-sim": "SNMP 模拟",
  "running-config": "运行配置",
};

export function formatDiscoveredVia(via?: string | null): string {
  if (!via) return "—";
  return DISCOVERED_VIA_LABEL[via] || via;
}

const ACCESS_MODE_LABEL: Record<string, string> = {
  access: "无标签",
  dot1q: "单标签",
  qinq: "双标签",
};

export function formatAccessMode(mode?: string | null): string {
  if (!mode) return "—";
  return ACCESS_MODE_LABEL[mode] || mode;
}

export function formatVlanLabel(
  accessMode?: string | null,
  sVid?: number | null,
  cVid?: number | null,
): string {
  if (accessMode === "access") return "无标签";
  if (cVid != null && sVid != null) return `S:${sVid}/C:${cVid}`;
  if (sVid != null) return `S:${sVid}`;
  return "—";
}

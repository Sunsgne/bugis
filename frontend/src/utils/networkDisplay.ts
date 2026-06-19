/** Compact interface labels and port metadata — locale-aware via i18n. */
import i18n from "../i18n";
import { tcStatic } from "../i18n/useTc";

const PORT_SUFFIX = /(\d+(?:\/\d+)+)\s*$/;

function tc(zh: string): string {
  return tcStatic(zh, i18n.language);
}

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
  [/^GigabitEthernet/i, "gigabit"],
  [/^GE/i, "GE"],
  [/^xe-/i, "10G"],
  [/^et-/i, "100G"],
  [/^ge-/i, "GE"],
];

export function interfacePortSuffix(name: string): string | null {
  const match = name.trim().match(PORT_SUFFIX);
  return match ? match[1] : null;
}

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

export function isVlanInterface(name: string): boolean {
  return /^(?:Vlan-interface|Vlanif|Vlan)\d+$/i.test(name.trim());
}

/** LAG / link aggregation (customer access may terminate on agg ports). */
export function isAggregatePort(name: string): boolean {
  const t = name.trim();
  return (
    /^Bridge-Aggregation\d+$/i.test(t)
    || /^Eth-Trunk\d+$/i.test(t)
    || /^Port-channel\d+$/i.test(t)
    || /^ae\d+$/i.test(t)
    || /^Bundle-Ether\d+$/i.test(t)
  );
}

const SYSTEM_IFACE = /loop(?:back)?|null0|inloop|console|register|meth\d|management|mgmt|vbdif/i;

/** Physical or aggregate port suitable for circuit L2 access — no VLAN/SVI/sub-if. */
export function isCircuitAccessPort(name: string): boolean {
  const trimmed = name.trim();
  if (!trimmed || SYSTEM_IFACE.test(trimmed)) return false;
  if (isVlanInterface(trimmed)) return false;
  if (isHuaweiSubinterface(trimmed)) return false;
  if (/\.\d+$/.test(trimmed) && /\d+\/\d+/.test(trimmed)) return false;
  if (isAggregatePort(trimmed)) return true;
  if (interfacePortSuffix(trimmed)) return true;
  if (/^(?:Twenty-Five|Hundred|Forty|Ten)?G(?:igabit)?(?:E|igabitEthernet)/i.test(trimmed)) return true;
  if (/^(?:25|100|10|40)GE/i.test(trimmed)) return true;
  if (/^(?:xe|et|ge)-/i.test(trimmed)) return true;
  if (/^GigabitEthernet/i.test(trimmed)) return true;
  return /^GE\d/i.test(trimmed);
}

export function formatInterfaceShort(name: string): string {
  const trimmed = name.trim();
  const vlanMatch = trimmed.match(/^(?:Vlan-interface|Vlanif|Vlan)(\d+)$/i);
  if (vlanMatch) return `VLAN·${vlanMatch[1]}`;
  const bAggMatch = trimmed.match(/^Bridge-Aggregation(\d+)$/i);
  if (bAggMatch) return `BAGG·${bAggMatch[1]}`;
  const sub = parseHuaweiSubinterface(trimmed);
  if (sub) {
    return `${formatInterfaceShort(sub.parent)}·${sub.vlan}`;
  }
  const suffix = interfacePortSuffix(trimmed);
  if (!suffix) return trimmed;

  for (const [pattern, label] of PREFIX_SPEED) {
    if (pattern.test(trimmed)) {
      const display = label === "gigabit" ? tc("千兆") : label;
      return `${display}·${suffix}`;
    }
  }
  return suffix.length + 3 < trimmed.length ? suffix : trimmed;
}

export function formatInterfaceTooltip(name: string): string {
  const short = formatInterfaceShort(name);
  return short === name ? name : i18n.t("network.fullName", { name });
}

export function formatOperStatus(status?: string | null): string {
  if (!status) return tc("—");
  const key = `status.port.${status.toLowerCase()}`;
  return i18n.t(key, {
    defaultValue: tc({ up: "在线", down: "离线", unknown: "未知" }[status.toLowerCase()] || status),
  });
}

export function formatDiscoveredVia(via?: string | null): string {
  if (!via) return tc("—");
  return i18n.t(`status.discoveredVia.${via}`, {
    defaultValue: tc({ snmp: "SNMP", "snmp-sim": "SNMP 模拟", "running-config": "运行配置" }[via] || via),
  });
}

export function formatAccessMode(mode?: string | null): string {
  if (!mode) return tc("—");
  return i18n.t(`status.accessMode.${mode}`, {
    defaultValue: tc({ access: "无标签", dot1q: "单标签", qinq: "双标签" }[mode] || mode),
  });
}

export function formatVlanLabel(
  accessMode?: string | null,
  sVid?: number | null,
  cVid?: number | null,
): string {
  if (accessMode === "access") return tc("无标签");
  if (cVid != null && sVid != null) return `S:${sVid}/C:${cVid}`;
  if (sVid != null) return `S:${sVid}`;
  return tc("—");
}

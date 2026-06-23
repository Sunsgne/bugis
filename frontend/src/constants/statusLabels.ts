/** Enum → label + color; labels resolve via i18n at read time. */
import i18n from "../i18n";
import { tcStatic } from "../i18n/useTc";
import { STATUS_COLORS } from "../i18n/helpers";

function tc(s: string): string {
  return tcStatic(s, i18n.language);
}

function tKey(key: string, fallback: string): string {
  return i18n.t(key, { defaultValue: fallback });
}

export const CIRCUIT_STATUS: Record<string, { label: string; color: string }> = new Proxy(
  {} as Record<string, { label: string; color: string }>,
  {
    get(_t, value: string) {
      if (value === "toJSON") return undefined;
      const color = STATUS_COLORS.circuit[value as keyof typeof STATUS_COLORS.circuit] || "default";
      const label = tKey(`status.circuit.${value}`, tc({
        draft: "草稿", pending: "待开通", provisioning: "开通中", active: "运行中",
        degraded: "降级", suspended: "已暂停", decommissioned: "已退服", failed: "失败",
      }[value] || String(value)));
      return { label, color };
    },
  },
);

export const WORK_ORDER_STATUS: Record<string, { label: string; color: string }> = new Proxy(
  {} as Record<string, { label: string; color: string }>,
  {
    get(_t, value: string) {
      if (value === "toJSON") return undefined;
      const color = STATUS_COLORS.workOrder[value as keyof typeof STATUS_COLORS.workOrder] || "default";
      const label = tKey(`status.workOrder.${value}`, tc({
        draft: "草稿", submitted: "已提交", approved: "已审批", rejected: "已驳回",
        scheduled: "已排期", running: "执行中", completed: "已完成", failed: "失败", cancelled: "已取消",
      }[value] || String(value)));
      return { label, color };
    },
  },
);

export const TENANT_STATUS: Record<string, { label: string; color: string }> = new Proxy(
  {} as Record<string, { label: string; color: string }>,
  {
    get(_t, value: string) {
      if (value === "toJSON") return undefined;
      const color = STATUS_COLORS.tenant[value as keyof typeof STATUS_COLORS.tenant] || "default";
      const label = tKey(`status.tenant.${value}`, tc({
        active: "正常", suspended: "已暂停", terminated: "已终止",
      }[value] || String(value)));
      return { label, color };
    },
  },
);

export const ALARM_KIND: Record<string, string> = new Proxy({} as Record<string, string>, {
  get(_t, value: string) {
    if (value === "toJSON") return undefined;
    return tKey(`status.alarmKind.${value}`, tc({
      tunnel_down: "隧道异常", circuit_interruption: "业务中断", sla_loss: "丢包超标",
      sla_latency: "时延超标", utilization: "带宽拥塞", health: "健康劣化",
      circuit_flap: "闪断频繁", link_utilization: "骨干拥塞", test: "测试通知",
    }[value] || String(value)));
  },
});

export const ALARM_SEVERITY: Record<string, { label: string; color: string }> = new Proxy(
  {} as Record<string, { label: string; color: string }>,
  {
    get(_t, value: string) {
      if (value === "toJSON") return undefined;
      const color = STATUS_COLORS.alarmSeverity[value as keyof typeof STATUS_COLORS.alarmSeverity] || "default";
      const label = tKey(`status.alarmSeverity.${value}`, tc({
        critical: "紧急 P1", major: "重要 P2", minor: "一般 P3", warning: "提示", info: "信息",
      }[value] || String(value)));
      return { label, color };
    },
  },
);

export const ALARM_STATUS: Record<string, { label: string; color: string }> = new Proxy(
  {} as Record<string, { label: string; color: string }>,
  {
    get(_t, value: string) {
      if (value === "toJSON") return undefined;
      const color = STATUS_COLORS.alarm[value as keyof typeof STATUS_COLORS.alarm] || "default";
      const label = tKey(`status.alarm.${value}`, tc({
        active: "活跃", acknowledged: "已确认", cleared: "已恢复",
      }[value] || String(value)));
      return { label, color };
    },
  },
);

export const SERVICE_TYPE: Record<string, string> = new Proxy({} as Record<string, string>, {
  get(_t, value: string) {
    if (value === "toJSON") return undefined;
    return tKey(`status.serviceType.${value}`, tc({
      l2vpn_evpn: "二层 EVPN", l3vpn_evpn: "三层 EVPN", remote_ipt: "Remote IPT",
      evpn_vpws: "EVPN VPWS", dci: "DCI 互联",
    }[value] || String(value)));
  },
});

export const CIRCUIT_PURPOSE: Record<string, { label: string; color: string }> = new Proxy(
  {} as Record<string, { label: string; color: string }>,
  {
    get(_t, value: string) {
      if (value === "toJSON") return undefined;
      const label = tKey(`status.circuitPurpose.${value}`, tc({
        business: "商务",
        test: "测试",
      }[value] || String(value)));
      const color = value === "test" ? "orange" : "blue";
      return { label, color };
    },
  },
);

export const TENANT_TYPE: Record<string, string> = new Proxy({} as Record<string, string>, {
  get(_t, value: string) {
    if (value === "toJSON") return undefined;
    return tKey(`status.tenantType.${value}`, tc({
      enterprise: "企业专线", hybrid_cloud: "混合云接入", public_cloud: "公有云接入", internal: "内部业务",
    }[value] || String(value)));
  },
});

export const WORK_ORDER_TYPE: Record<string, string> = new Proxy({} as Record<string, string>, {
  get(_t, value: string) {
    if (value === "toJSON") return undefined;
    return tKey(`status.workOrderType.${value}`, tc({
      provision: "开通", modify: "变更", decommission: "拆除", migrate: "迁移",
    }[value] || String(value)));
  },
});

export const OVERLAY_SOURCE: Record<string, string> = new Proxy({} as Record<string, string>, {
  get(_t, value: string) {
    if (value === "toJSON") return undefined;
    return tKey(`status.overlaySource.${value}`, tc({
      platform: "平台纳管", network_only: "现网占用",
    }[value] || String(value)));
  },
});

export function statusMeta(
  map: Record<string, { label: string; color: string }>,
  value: string | undefined | null,
): { label: string; color: string } {
  if (!value) return { label: tc("—"), color: "default" };
  return map[value] || { label: value, color: "default" };
}

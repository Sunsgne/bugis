/** Centralized enum → 中文标签 + 颜色映射，避免各页面裸露英文枚举。 */

export const CIRCUIT_STATUS: Record<string, { label: string; color: string }> = {
  draft: { label: "草稿", color: "default" },
  pending: { label: "待开通", color: "gold" },
  provisioning: { label: "开通中", color: "processing" },
  active: { label: "运行中", color: "green" },
  degraded: { label: "降级", color: "orange" },
  suspended: { label: "已暂停", color: "volcano" },
  decommissioned: { label: "已退服", color: "default" },
  failed: { label: "失败", color: "red" },
};

export const WORK_ORDER_STATUS: Record<string, { label: string; color: string }> = {
  draft: { label: "草稿", color: "default" },
  submitted: { label: "已提交", color: "blue" },
  approved: { label: "已审批", color: "cyan" },
  rejected: { label: "已驳回", color: "red" },
  scheduled: { label: "已排期", color: "geekblue" },
  running: { label: "执行中", color: "processing" },
  completed: { label: "已完成", color: "green" },
  failed: { label: "失败", color: "red" },
  cancelled: { label: "已取消", color: "default" },
};

export const TENANT_STATUS: Record<string, { label: string; color: string }> = {
  active: { label: "正常", color: "green" },
  suspended: { label: "已暂停", color: "volcano" },
  terminated: { label: "已终止", color: "default" },
};

export const ALARM_STATUS: Record<string, { label: string; color: string }> = {
  active: { label: "活跃", color: "red" },
  acknowledged: { label: "已确认", color: "gold" },
  cleared: { label: "已恢复", color: "green" },
};

export const SERVICE_TYPE: Record<string, string> = {
  l2vpn_evpn: "二层 EVPN",
  l3vpn_evpn: "三层 EVPN",
  remote_ipt: "Remote IPT",
  evpn_vpws: "EVPN VPWS",
  dci: "DCI 互联",
};

export function statusMeta(
  map: Record<string, { label: string; color: string }>,
  value: string | undefined | null,
): { label: string; color: string } {
  if (!value) return { label: "—", color: "default" };
  return map[value] || { label: value, color: "default" };
}

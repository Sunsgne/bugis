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

export const ALARM_KIND: Record<string, string> = {
  tunnel_down: "隧道异常",
  circuit_interruption: "业务中断",
  sla_loss: "丢包超标",
  sla_latency: "时延超标",
  utilization: "带宽拥塞",
  health: "健康劣化",
  circuit_flap: "闪断频繁",
  link_utilization: "骨干拥塞",
  test: "测试通知",
};

export const ALARM_SEVERITY: Record<string, { label: string; color: string }> = {
  critical: { label: "紧急 P1", color: "red" },
  major: { label: "重要 P2", color: "volcano" },
  minor: { label: "一般 P3", color: "orange" },
  warning: { label: "提示", color: "gold" },
  info: { label: "信息", color: "blue" },
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

/** Translate backend / API Chinese copy for English locale. */

type TcFn = (zh: string) => string;

const WO_PATTERNS: Array<{ re: RegExp; en: (...m: string[]) => string }> = [
  {
    re: /^已加入开通队列，后台异步执行（可在工单详情查看进度）$/,
    en: () =>
      "Queued for provisioning; running asynchronously in the background (see work order details for progress)",
  },
  {
    re: /^已保存 (\d+) 台设备的变更前现网配置快照（变更对比 \/ 应急还原）$/,
    en: (n) =>
      `Saved pre-change live config snapshots for ${n} device(s) (change comparison / emergency restore)`,
  },
  {
    re: /^\[Bugis SDN\] apply VNI (\d+): (\d+) 条 EVPN 路由$/,
    en: (vni, n) => `[Bugis SDN] apply VNI ${vni}: ${n} EVPN routes`,
  },
  {
    re: /^\[Bugis SDN\] 已回滚控制面 VNI (\d+)$/,
    en: (vni) => `[Bugis SDN] rolled back control-plane VNI ${vni}`,
  },
  {
    re: /^Bugis 控制器错误: (.+)$/,
    en: (msg) => `Bugis controller error: ${msg}`,
  },
  {
    re: /^控制器 (\d+) 不存在$/,
    en: (id) => `Controller ${id} not found`,
  },
  {
    re: /^控制器下发错误: (.+)$/,
    en: (msg) => `Controller push error: ${msg}`,
  },
  {
    re: /^工单已编辑 \((.+)\)$/,
    en: (fields) => `Work order updated (${fields})`,
  },
  {
    re: /^工单已取消$/,
    en: () => "Work order cancelled",
  },
  {
    re: /^已自动清除 (\d+) 条活跃告警$/,
    en: (n) => `Cleared ${n} active alarm(s)`,
  },
  {
    re: /^预检\[(\w+)\] ([^:]+): (.+)$/,
    en: (level, code, msg) => `Pre-check [${level}] ${code}: ${msg}`,
  },
  {
    re: /^预检未通过，存在 (\d+) 个错误，已阻断下发$/,
    en: (n) => `Pre-check failed with ${n} error(s); push blocked`,
  },
  {
    re: /^端点变更：先拆除 (\d+) 个旧接入配置$/,
    en: (n) => `Endpoint change: tearing down ${n} previous access config(s) first`,
  },
  {
    re: /^\[控制器\] ([^ ]+) ([^:]+): (.+)$/,
    en: (type, name, op) => `[Controller] ${type} ${name}: ${op}`,
  },
  {
    re: /^回滚 (.+) 时发生异常: (.+)$/,
    en: (name, msg) => `Rollback error on ${name}: ${msg}`,
  },
];

const API_PATTERNS: Array<{ re: RegExp; en: (...m: string[]) => string }> = [
  {
    re: /^平台内置自研 EVPN 控制平面 v([^，]+)，无需手动添加或配置北向地址$/,
    en: (ver) =>
      `Built-in EVPN control plane v${ver}; no manual northbound address configuration required`,
  },
  {
    re: /^Bugis SDN 控制器$/,
    en: () => "Bugis SDN Controller",
  },
  {
    re: /^定时自动拉取已开启（间隔 (\d+) 秒）$/,
    en: (sec) => `Scheduled automatic pull is enabled (interval ${sec} seconds)`,
  },
];

function matchPatterns(text: string, patterns: typeof WO_PATTERNS, isEn: boolean): string | null {
  if (!isEn) return null;
  for (const { re, en } of patterns) {
    const m = text.match(re);
    if (m) return en(...m.slice(1));
  }
  return null;
}

export function translateApiText(text: string, tc: TcFn, isEn: boolean): string {
  if (!text || !isEn) return text;
  const fromPattern =
    matchPatterns(text, WO_PATTERNS, true) ?? matchPatterns(text, API_PATTERNS, true);
  if (fromPattern) return fromPattern;
  const translated = tc(text);
  return translated !== text ? translated : text;
}

export function translateWorkOrderMessage(message: string, tc: TcFn, isEn: boolean): string {
  return translateApiText(message, tc, isEn);
}

/**
 * @deprecated Use useTc() or useTranslation() — kept for gradual migration.
 */
import i18n from "../i18n";
import { tcStatic } from "../i18n/useTc";

function tc(s: string): string {
  return tcStatic(s, i18n.language);
}

export const brand = {
  get product() { return "Bugis Network"; },
  get tagline() { return tc("DCI · EVPN 全域智能运营"); },
  get header() { return tc("DCI / EVPN 全域网络运营中枢"); },
  get loginTitle() { return "Bugis Network"; },
  get loginSubtitle() { return "Multi-Vendor · BGP EVPN · Intelligent Fabric Ops"; },
  get heroTitle() { return tc("DCI / EVPN 运营驾驶舱"); },
  get heroSubtitle() { return tc("多厂商异构 · VXLAN / SR-MPLS EVPN · 自研 SDN · 跨域 DCI"); },
};

export const nav = {
  groups: {
    get overview() { return tc("业务总览"); },
    get resources() { return tc("客户管理"); },
    get circuits() { return tc("专线业务"); },
    get network() { return tc("网络与控制面"); },
    get ops() { return tc("可观测性"); },
    get system() { return tc("平台治理"); },
  },
  items: {
    get dashboard() { return tc("运营驾驶舱"); },
    get tenants() { return tc("客户"); },
    get sites() { return tc("Fabric 站点"); },
    get devices() { return tc("网络设备"); },
    get circuits() { return tc("专线管理"); },
    get workOrders() { return tc("操作日志"); },
    get controllers() { return tc("SDN 控制器"); },
    get controlPlane() { return tc("控制面视图"); },
    get config() { return tc("配置中心"); },
    get topology() { return tc("物理拓扑"); },
    get capacity() { return tc("容量规划"); },
    get monitoring() { return tc("流量洞察"); },
    get alarms() { return tc("告警态势"); },
    get settings() { return tc("平台设置"); },
    get notifications() { return tc("通知渠道"); },
    get integrations() { return tc("北向集成"); },
    get users() { return tc("用户权限"); },
    get audit() { return tc("操作审计"); },
  },
} as const;

export const action = {
  get create() { return tc("创建"); },
  get createCircuit() { return tc("开通专线"); },
  get save() { return tc("保存"); },
  get edit() { return tc("编辑"); },
  get delete() { return tc("删除"); },
  get export() { return tc("导出"); },
  get import() { return tc("导入"); },
  get refresh() { return tc("刷新"); },
  get login() { return tc("进入平台"); },
  get logout() { return tc("退出登录"); },
  get confirm() { return tc("确认"); },
  get cancel() { return tc("取消"); },
  get viewAll() { return tc("全域视图"); },
  get learnNow() { return tc("立即学习"); },
  get ack() { return tc("确认告警"); },
  get changePassword() { return tc("修改密码"); },
} as const;

export const empty = {
  get default() { return tc("暂无记录"); },
  get circuits() { return tc("暂无专线 · 点击右上角创建首条 Circuit"); },
  get devices() { return tc("暂无设备 · 从导入或纳管开始"); },
  get snapshots() { return tc("尚无配置快照 · 可先备份或执行现网学习"); },
  get traffic() { return tc("流量数据采集中 · 巡检引擎即将写入时序"); },
  get alarms() { return tc("全网健康 · 零活跃告警"); },
  get data() { return tc("数据加载后将在此呈现"); },
  get selectDevice() { return tc("← 选择左侧设备以查看配置"); },
  get noLearn() { return tc("尚未同步现网配置 · 一键拉取 Running Config"); },
} as const;

export const toast = {
  get saved() { return tc("已保存"); },
  get deleted() { return tc("已删除"); },
  get created() { return tc("创建成功"); },
  get failed() { return tc("操作失败，请重试"); },
  get loginOk() { return tc("欢迎回来"); },
  get loginFail() { return tc("凭证无效，请检查后重试"); },
} as const;

export const page = {
  get dashboard() { return tc("运营驾驶舱"); },
  get tenants() { return tc("客户"); },
  get sites() { return tc("Fabric 站点"); },
  get devices() { return tc("网络设备"); },
  get circuits() { return tc("专线管理"); },
  get circuitsFull() { return tc("专线管理 · Circuit Studio"); },
  get workOrders() { return tc("操作日志"); },
  get config() { return tc("配置中心"); },
  get controllers() { return tc("SDN 控制器"); },
  get controlPlane() { return tc("控制面视图"); },
  get topology() { return tc("物理拓扑"); },
  get capacity() { return tc("容量规划"); },
  get monitoring() { return tc("流量洞察"); },
  get alarms() { return tc("告警态势"); },
  get settings() { return tc("平台设置"); },
  get audit() { return tc("操作审计"); },
  get users() { return tc("用户权限"); },
  get notifications() { return tc("通知渠道"); },
  get integrations() { return tc("北向集成"); },
} as const;

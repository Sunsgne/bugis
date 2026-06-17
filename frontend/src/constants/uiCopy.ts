/** Platform-wide UI copy — modern, concise, enterprise tone. */

export const brand = {
  product: "Bugis Network",
  tagline: "DCI · EVPN 全域智能运营",
  header: "DCI / EVPN 全域网络运营中枢",
  loginTitle: "Bugis Network",
  loginSubtitle: "Multi-Vendor · BGP EVPN · Intelligent Fabric Ops",
  heroTitle: "DCI / EVPN 运营驾驶舱",
  heroSubtitle: "多厂商异构 · VXLAN / SR-MPLS EVPN · 自研 SDN · 跨域 DCI",
} as const;

export const nav = {
  groups: {
    overview: "业务总揽",
    resources: "客户管理",
    circuits: "专线业务",
    network: "网络与控制面",
    ops: "可观测性",
    system: "平台治理",
  },
  items: {
    dashboard: "运营驾驶舱",
    tenants: "客户",
    sites: "Fabric 站点",
    devices: "网络设备",
    circuits: "专线编排",
    workOrders: "编排工单",
    controllers: "SDN 控制器",
    controlPlane: "控制面视图",
    config: "配置中心",
    topology: "物理拓扑",
    capacity: "容量规划",
    monitoring: "流量洞察",
    alarms: "告警态势",
    settings: "平台设置",
    notifications: "通知渠道",
    integrations: "北向集成",
    users: "用户权限",
    audit: "操作审计",
  },
} as const;

export const action = {
  create: "创建",
  createCircuit: "开通专线",
  save: "保存",
  delete: "删除",
  export: "导出",
  import: "导入",
  refresh: "刷新",
  login: "进入平台",
  logout: "退出登录",
  confirm: "确认",
  cancel: "取消",
  viewAll: "全域视图",
  learnNow: "立即学习",
} as const;

export const empty = {
  default: "暂无记录",
  circuits: "暂无专线 · 点击右上角创建首条 Circuit",
  devices: "暂无设备 · 从导入或纳管开始",
  snapshots: "尚无配置快照 · 可先备份或执行现网学习",
  traffic: "流量数据采集中 · 巡检引擎即将写入时序",
  alarms: "全网健康 · 零活跃告警",
  data: "数据加载后将在此呈现",
  selectDevice: "← 选择左侧设备以查看配置",
  noLearn: "尚未同步现网配置 · 一键拉取 Running Config",
} as const;

export const toast = {
  saved: "已保存",
  deleted: "已删除",
  created: "创建成功",
  failed: "操作失败，请重试",
  loginOk: "欢迎回来",
  loginFail: "凭证无效，请检查后重试",
} as const;

/** Reusable page titles */
export const page = {
  tenants: "客户",
  sites: "Fabric 站点",
  devices: "网络设备",
  circuits: "专线编排",
  circuitsFull: "专线编排 · Circuit Studio",
  workOrders: "编排工单",
  config: "配置中心",
  controllers: "SDN 控制器",
  controlPlane: "控制面视图",
  topology: "物理拓扑",
  capacity: "容量规划",
  monitoring: "流量洞察",
  alarms: "告警态势",
  settings: "平台设置",
  audit: "操作审计",
  users: "用户权限",
  notifications: "通知渠道",
  integrations: "北向集成",
} as const;

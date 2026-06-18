#!/usr/bin/env python3
"""Generate zh.json / en.json from hardcoded Chinese strings and known translations."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OUT_ZH = ROOT / "src/i18n/locales/zh.json"
OUT_EN = ROOT / "src/i18n/locales/en.json"

ZH_RE = re.compile(r"[\u4e00-\u9fff]")
STR_PAT = re.compile(r'(["\'`])(?:(?=(\\?))\2.)*?\1', re.DOTALL)

# Hand-crafted EN for status / form / common (quality translations)
MANUAL_EN: dict[str, str] = {
    # statusLabels
    "草稿": "Draft",
    "待开通": "Pending",
    "开通中": "Provisioning",
    "运行中": "Active",
    "降级": "Degraded",
    "已暂停": "Suspended",
    "已退服": "Decommissioned",
    "失败": "Failed",
    "已提交": "Submitted",
    "已审批": "Approved",
    "已驳回": "Rejected",
    "已排期": "Scheduled",
    "执行中": "Running",
    "已完成": "Completed",
    "已取消": "Cancelled",
    "正常": "Active",
    "已终止": "Terminated",
    "隧道异常": "Tunnel fault",
    "业务中断": "Service interruption",
    "丢包超标": "Packet loss exceeded",
    "时延超标": "Latency exceeded",
    "带宽拥塞": "Bandwidth congestion",
    "健康劣化": "Health degraded",
    "闪断频繁": "Frequent flaps",
    "骨干拥塞": "Backbone congestion",
    "测试通知": "Test notification",
    "紧急 P1": "Critical P1",
    "重要 P2": "Major P2",
    "一般 P3": "Minor P3",
    "提示": "Warning",
    "信息": "Info",
    "活跃": "Active",
    "已确认": "Acknowledged",
    "已恢复": "Cleared",
    "二层 EVPN": "L2 EVPN",
    "三层 EVPN": "L3 EVPN",
    "DCI 互联": "DCI interconnect",
    # common table/form
    "状态": "Status",
    "类型": "Type",
    "操作": "Actions",
    "设备": "Device",
    "名称": "Name",
    "客户": "Tenant",
    "角色": "Role",
    "编码": "Code",
    "来源": "Source",
    "用户名": "Username",
    "描述": "Description",
    "时间": "Time",
    "备注": "Notes",
    "邮箱": "Email",
    "取消": "Cancel",
    "保存": "Save",
    "创建": "Create",
    "编辑": "Edit",
    "删除": "Delete",
    "导出": "Export",
    "导入": "Import",
    "刷新": "Refresh",
    "确认": "Confirm",
    "开": "On",
    "关": "Off",
    "可选": "Optional",
    "在线": "Up",
    "离线": "Down",
    "未知": "Unknown",
    "暂无数据": "No data",
    "暂无记录": "No records",
    "保存失败": "Save failed",
    "已保存": "Saved",
    "已删除": "Deleted",
    "创建成功": "Created",
    "操作失败，请重试": "Operation failed, please retry",
    "欢迎回来": "Welcome back",
    "凭证无效，请检查后重试": "Invalid credentials",
    "加载中…": "Loading…",
    "客户自助门户": "Customer self-service portal",
    "专线自助服务": "Circuit self-service",
    "账号与安全": "Account & security",
    "退出登录": "Sign out",
    "平台设置": "Platform settings",
    "千兆": "Gigabit",
    "接口全名：": "Full name: ",
    "SNMP 模拟": "SNMP simulated",
    "运行配置": "Running config",
    "无标签": "Untagged",
    "单标签": "Single tag",
    "双标签": "Double tag",
    # auth
    "请输入用户名和密码": "Enter username and password",
    "请先完成人机验证": "Complete CAPTCHA first",
    "请输入双因素验证码": "Enter two-factor code",
    "需要完成人机验证后重试": "Complete CAPTCHA and retry",
    "请输入验证码": "Enter verification code",
    "验证码错误": "Invalid verification code",
    "验证码已发送至邮箱": "Code sent to email",
    "邮件发送失败": "Failed to send email",
    "请输入用户名或邮箱": "Enter username or email",
    "若账号存在，验证码已发送至邮箱": "If the account exists, a code was sent to email",
    "发送失败，请稍后再试": "Send failed, try again later",
    "新密码至少 8 位": "New password must be at least 8 characters",
    "两次输入的密码不一致": "Passwords do not match",
    "密码已重置，请使用新密码登录": "Password reset; sign in with your new password",
    "重置失败，请检查验证码": "Reset failed; check verification code",
    "双因素验证": "Two-factor authentication",
    "找回密码": "Forgot password",
    "重置密码": "Reset password",
    "人机验证组件加载失败": "CAPTCHA failed to load",
    "验证码": "Verification code",
    "6 位数字": "6-digit code",
    "发送邮件验证码": "Send email code",
    "验证并登录": "Verify & sign in",
    "返回登录": "Back to sign in",
    "用户名或邮箱": "Username or email",
    "请输入用户名或绑定邮箱": "Username or registered email",
    "发送验证码": "Send code",
    "已有验证码？": "Already have a code?",
    "邮件验证码": "Email verification code",
    "新密码": "New password",
    "至少 8 位": "At least 8 characters",
    "确认新密码": "Confirm new password",
    "请再次输入新密码": "Re-enter new password",
    "重置密码并返回登录": "Reset password & sign in",
    "重新获取验证码": "Resend code",
    "密码": "Password",
    "忘记密码？": "Forgot password?",
    "请输入用户名": "Enter username",
    "请输入密码": "Enter password",
    "登录中…": "Signing in…",
    "已要求人机验证，请在系统设置中配置 Turnstile Site Key": "CAPTCHA required; configure Turnstile Site Key in settings",
    "EVPN VXLAN 智能编排": "EVPN VXLAN orchestration",
    "意图驱动，多厂商一键开通": "Intent-driven multi-vendor provisioning",
    "跨 DC / 跨域互联": "Cross-DC / cross-domain interconnect",
    "DCI 专线全生命周期管理": "DCI circuit lifecycle management",
    "多厂商统一纳管": "Unified multi-vendor management",
    "华三 / 华为 / 思科 / Juniper": "H3C / Huawei / Cisco / Juniper",
}

# Structured namespaces merged into final JSON
STRUCTURED_ZH = {
    "brand": {
        "product": "Bugis Network",
        "tagline": "DCI · EVPN 全域智能运营",
        "header": "DCI / EVPN 全域网络运营中枢",
        "loginTitle": "Bugis Network",
        "loginSubtitle": "Multi-Vendor · BGP EVPN · Intelligent Fabric Ops",
        "heroTitle": "DCI / EVPN 运营驾驶舱",
        "heroSubtitle": "多厂商异构 · VXLAN / SR-MPLS EVPN · 自研 SDN · 跨域 DCI",
    },
    "action": {
        "save": "保存",
        "cancel": "取消",
        "logout": "退出登录",
        "changePassword": "修改密码",
        "accountSettings": "个人设置",
        "create": "创建",
        "createCircuit": "开通专线",
        "edit": "编辑",
        "delete": "删除",
        "export": "导出",
        "import": "导入",
        "refresh": "刷新",
        "login": "进入平台",
        "confirm": "确认",
        "viewAll": "全域视图",
        "learnNow": "立即学习",
        "ack": "确认告警",
    },
    "empty": {
        "default": "暂无记录",
        "circuits": "暂无专线 · 点击右上角创建首条 Circuit",
        "devices": "暂无设备 · 从导入或纳管开始",
        "snapshots": "尚无配置快照 · 可先备份或执行现网学习",
        "traffic": "流量数据采集中 · 巡检引擎即将写入时序",
        "alarms": "全网健康 · 零活跃告警",
        "data": "数据加载后将在此呈现",
        "selectDevice": "← 选择左侧设备以查看配置",
        "noLearn": "尚未同步现网配置 · 一键拉取 Running Config",
    },
    "toast": {
        "saved": "已保存",
        "deleted": "已删除",
        "created": "创建成功",
        "failed": "操作失败，请重试",
        "loginOk": "欢迎回来",
        "loginFail": "凭证无效，请检查后重试",
    },
    "page": {
        "dashboard": "运营驾驶舱",
        "tenants": "客户",
        "sites": "Fabric 站点",
        "devices": "网络设备",
        "circuits": "专线管理",
        "circuitsFull": "专线管理 · Circuit Studio",
        "workOrders": "操作日志",
        "config": "配置中心",
        "controllers": "SDN 控制器",
        "controlPlane": "控制面视图",
        "topology": "物理拓扑",
        "capacity": "容量规划",
        "monitoring": "流量洞察",
        "alarms": "告警态势",
        "settings": "平台设置",
        "audit": "操作审计",
        "users": "用户权限",
        "notifications": "通知渠道",
        "integrations": "北向集成",
    },
    "status": {
        "circuit": {
            "draft": "草稿", "pending": "待开通", "provisioning": "开通中",
            "active": "运行中", "degraded": "降级", "suspended": "已暂停",
            "decommissioned": "已退服", "failed": "失败",
        },
        "workOrder": {
            "draft": "草稿", "submitted": "已提交", "approved": "已审批",
            "rejected": "已驳回", "scheduled": "已排期", "running": "执行中",
            "completed": "已完成", "failed": "失败", "cancelled": "已取消",
        },
        "tenant": {"active": "正常", "suspended": "已暂停", "terminated": "已终止"},
        "alarmKind": {
            "tunnel_down": "隧道异常", "circuit_interruption": "业务中断",
            "sla_loss": "丢包超标", "sla_latency": "时延超标",
            "utilization": "带宽拥塞", "health": "健康劣化",
            "circuit_flap": "闪断频繁", "link_utilization": "骨干拥塞", "test": "测试通知",
        },
        "alarmSeverity": {
            "critical": "紧急 P1", "major": "重要 P2", "minor": "一般 P3",
            "warning": "提示", "info": "信息",
        },
        "alarm": {"active": "活跃", "acknowledged": "已确认", "cleared": "已恢复"},
        "serviceType": {
            "l2vpn_evpn": "二层 EVPN", "l3vpn_evpn": "三层 EVPN",
            "remote_ipt": "Remote IPT", "evpn_vpws": "EVPN VPWS", "dci": "DCI 互联",
        },
        "device": {"online": "在线", "offline": "离线", "maintenance": "维护", "unknown": "未知"},
        "port": {"up": "在线", "down": "离线", "unknown": "未知"},
        "accessMode": {"access": "无标签", "dot1q": "单标签", "qinq": "双标签"},
        "discoveredVia": {"snmp": "SNMP", "snmp-sim": "SNMP 模拟", "running-config": "运行配置"},
    },
    "form": {
        "vendor": {
            "h3c": "H3C 新华三", "huawei": "Huawei 华为", "juniper": "Juniper 瞻博",
            "arista": "Arista", "cisco": "Cisco 思科", "frr": "FRR 开源路由",
        },
        "deviceRole": {
            "spine": "Spine 核心", "leaf": "Leaf 接入", "border_leaf": "Border Leaf 边界",
            "vtep": "VTEP 隧道端点", "pe": "PE 提供商边缘", "p": "P 核心路由器",
            "rr": "RR 路由反射器", "dci_gw": "DCI Gateway 互联网关", "cpe": "CPE 客户设备",
        },
        "managementTransport": {
            "auto": "自动（按厂商默认）", "netconf": "NETCONF", "ssh": "SSH CLI",
        },
    },
    "table": {
        "noData": "暂无数据",
        "range": "第 {{start}}–{{end}} 条，共 {{total}} 条",
        "totalOnly": "共 {{total}} 条",
    },
    "network": {
        "gigabit": "千兆",
        "fullName": "接口全名：{{name}}",
    },
    "settings": {
        "title": "平台设置",
        "intro": "集中管理品牌外观、平台运行参数、告警策略、SNMP/邮件、北向集成与用户权限。修改后即时生效。",
        "nav": {
            "brand": "品牌外观", "general": "平台运行", "configLearn": "配置管理",
            "alarms": "告警阈值", "baseline": "设备基线", "smtp": "邮件 SMTP",
            "management": "南向接口", "snmp": "SNMP 采集", "integration": "北向集成",
            "security": "安全认证", "notifications": "通知渠道", "users": "用户权限", "audit": "操作审计",
        },
    },
    "portal": {
        "selfService": "客户自助门户",
        "circuitService": "专线自助服务",
        "loading": "加载中…",
        "menu": {
            "dashboard": "总览", "circuits": "我的专线", "traffic": "流量洞察", "account": "账号与安全",
        },
        "roleTenantAdmin": "租户管理员",
        "roleTenantViewer": "租户只读",
        "portalLabel": "客户门户",
    },
    "common": {
        "dash": "—",
        "on": "开",
        "off": "关",
        "optional": "可选",
        "loading": "加载中…",
    },
}

STRUCTURED_EN = {
    "brand": {
        "product": "Bugis Network",
        "tagline": "DCI · EVPN Intelligent Operations",
        "header": "DCI / EVPN Network Operations Hub",
        "loginTitle": "Bugis Network",
        "loginSubtitle": "Multi-Vendor · BGP EVPN · Intelligent Fabric Ops",
        "heroTitle": "DCI / EVPN Operations Dashboard",
        "heroSubtitle": "Multi-vendor · VXLAN / SR-MPLS EVPN · SDN · Cross-domain DCI",
    },
    "action": {
        "save": "Save", "cancel": "Cancel", "logout": "Sign out",
        "changePassword": "Change password", "accountSettings": "Account settings",
        "create": "Create", "createCircuit": "Provision circuit", "edit": "Edit",
        "delete": "Delete", "export": "Export", "import": "Import", "refresh": "Refresh",
        "login": "Sign in", "confirm": "Confirm", "viewAll": "Global view",
        "learnNow": "Learn now", "ack": "Acknowledge alarm",
    },
    "empty": {
        "default": "No records",
        "circuits": "No circuits · Create your first circuit",
        "devices": "No devices · Import or onboard to start",
        "snapshots": "No config snapshots · Backup or learn from network",
        "traffic": "Collecting traffic data · Telemetry pending",
        "alarms": "Network healthy · No active alarms",
        "data": "Data will appear here once loaded",
        "selectDevice": "← Select a device on the left",
        "noLearn": "No learned config · Pull running config",
    },
    "toast": {
        "saved": "Saved", "deleted": "Deleted", "created": "Created",
        "failed": "Operation failed, please retry",
        "loginOk": "Welcome back", "loginFail": "Invalid credentials",
    },
    "page": {
        "dashboard": "Dashboard", "tenants": "Tenants", "sites": "Fabric Sites",
        "devices": "Devices", "circuits": "Circuits",
        "circuitsFull": "Circuits · Circuit Studio", "workOrders": "Work Orders",
        "config": "Config Center", "controllers": "SDN Controllers",
        "controlPlane": "Control Plane", "topology": "Topology",
        "capacity": "Capacity", "monitoring": "Traffic Insights",
        "alarms": "Alarms", "settings": "Settings", "audit": "Audit",
        "users": "Users", "notifications": "Notifications", "integrations": "Integrations",
    },
    "status": {
        "circuit": {
            "draft": "Draft", "pending": "Pending", "provisioning": "Provisioning",
            "active": "Active", "degraded": "Degraded", "suspended": "Suspended",
            "decommissioned": "Decommissioned", "failed": "Failed",
        },
        "workOrder": {
            "draft": "Draft", "submitted": "Submitted", "approved": "Approved",
            "rejected": "Rejected", "scheduled": "Scheduled", "running": "Running",
            "completed": "Completed", "failed": "Failed", "cancelled": "Cancelled",
        },
        "tenant": {"active": "Active", "suspended": "Suspended", "terminated": "Terminated"},
        "alarmKind": {
            "tunnel_down": "Tunnel fault", "circuit_interruption": "Service interruption",
            "sla_loss": "Packet loss exceeded", "sla_latency": "Latency exceeded",
            "utilization": "Bandwidth congestion", "health": "Health degraded",
            "circuit_flap": "Frequent flaps", "link_utilization": "Backbone congestion", "test": "Test",
        },
        "alarmSeverity": {
            "critical": "Critical P1", "major": "Major P2", "minor": "Minor P3",
            "warning": "Warning", "info": "Info",
        },
        "alarm": {"active": "Active", "acknowledged": "Acknowledged", "cleared": "Cleared"},
        "serviceType": {
            "l2vpn_evpn": "L2 EVPN", "l3vpn_evpn": "L3 EVPN",
            "remote_ipt": "Remote IPT", "evpn_vpws": "EVPN VPWS", "dci": "DCI interconnect",
        },
        "device": {"online": "Up", "offline": "Down", "maintenance": "Maintenance", "unknown": "Unknown"},
        "port": {"up": "Up", "down": "Down", "unknown": "Unknown"},
        "accessMode": {"access": "Untagged", "dot1q": "Single tag", "qinq": "Double tag"},
        "discoveredVia": {"snmp": "SNMP", "snmp-sim": "SNMP simulated", "running-config": "Running config"},
    },
    "form": {
        "vendor": {
            "h3c": "H3C", "huawei": "Huawei", "juniper": "Juniper",
            "arista": "Arista", "cisco": "Cisco", "frr": "FRR",
        },
        "deviceRole": {
            "spine": "Spine", "leaf": "Leaf", "border_leaf": "Border Leaf",
            "vtep": "VTEP", "pe": "PE", "p": "P router",
            "rr": "Route Reflector", "dci_gw": "DCI Gateway", "cpe": "CPE",
        },
        "managementTransport": {
            "auto": "Auto (vendor default)", "netconf": "NETCONF", "ssh": "SSH CLI",
        },
    },
    "table": {
        "noData": "No data",
        "range": "{{start}}–{{end}} of {{total}}",
        "totalOnly": "{{total}} total",
    },
    "network": {"gigabit": "Gigabit", "fullName": "Full name: {{name}}"},
    "settings": {
        "title": "Platform settings",
        "intro": "Manage branding, runtime, alarms, SNMP/email, integrations and users. Changes apply immediately.",
        "nav": {
            "brand": "Branding", "general": "Runtime", "configLearn": "Config management",
            "alarms": "Alarm thresholds", "baseline": "Device baseline", "smtp": "Email SMTP",
            "management": "Southbound", "snmp": "SNMP collection", "integration": "Northbound",
            "security": "Security", "notifications": "Notifications", "users": "Users", "audit": "Audit",
        },
    },
    "portal": {
        "selfService": "Customer self-service portal",
        "circuitService": "Circuit self-service",
        "loading": "Loading…",
        "menu": {
            "dashboard": "Overview", "circuits": "My circuits", "traffic": "Traffic", "account": "Account & security",
        },
        "roleTenantAdmin": "Tenant admin",
        "roleTenantViewer": "Tenant viewer",
        "portalLabel": "Customer portal",
    },
    "common": {"dash": "—", "on": "On", "off": "Off", "optional": "Optional", "loading": "Loading…"},
}


def deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def flatten(d: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def unflatten(flat: dict[str, str]) -> dict:
    root: dict = {}
    for key, val in sorted(flat.items()):
        parts = key.split(".")
        cur = root
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = val
    return root


def slug(s: str) -> str:
    h = hashlib.md5(s.encode()).hexdigest()[:8]
    return h


def extract_strings() -> set[str]:
    found: set[str] = set()
    for p in SRC.rglob("*"):
        if p.suffix not in (".ts", ".tsx"):
            continue
        if "i18n/locales" in str(p):
            continue
        text = p.read_text(encoding="utf-8")
        for m in STR_PAT.finditer(text):
            s = m.group(0)[1:-1]
            if ZH_RE.search(s) and len(s) < 300:
                start = m.start()
                line_start = text.rfind("\n", 0, start) + 1
                line = text[line_start : text.find("\n", start)]
                if line.strip().startswith("//") or line.strip().startswith("*"):
                    continue
                found.add(s)
    return found


def translate_auto(zh: str) -> str:
    if zh in MANUAL_EN:
        return MANUAL_EN[zh]
    # crude fallback: keep technical tokens, mark for review
    return f"[EN] {zh}"


def main():
    # load existing nav/account/monitor from current zh.json
    existing_zh = json.loads((ROOT / "src/i18n/locales/zh.json").read_text(encoding="utf-8"))
    existing_en = json.loads((ROOT / "src/i18n/locales/en.json").read_text(encoding="utf-8"))

    zh_flat = flatten(deep_merge(existing_zh, STRUCTURED_ZH))
    en_flat = flatten(deep_merge(existing_en, STRUCTURED_EN))

    # auto keys for remaining extracted strings
    known_zh = set(zh_flat.values())
    auto_map: dict[str, str] = {}
    for s in sorted(extract_strings()):
        if s in known_zh:
            continue
        key = f"auto.{slug(s)}"
        auto_map[key] = s
        zh_flat[key] = s
        en_flat[key] = translate_auto(s)

    zh_out = unflatten(zh_flat)
    en_out = unflatten(en_flat)

    OUT_ZH.write_text(json.dumps(zh_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_EN.write_text(json.dumps(en_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    map_path = ROOT / "scripts/i18n-string-map.json"
    reverse = {v: k for k, v in zh_flat.items()}
    map_path.write_text(json.dumps(reverse, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(zh_flat)} keys ({len(auto_map)} auto); map at {map_path}")


if __name__ == "__main__":
    main()

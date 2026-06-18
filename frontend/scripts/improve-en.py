#!/usr/bin/env python3
"""Improve auto-generated English translations using pattern rules."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_PATH = ROOT / "src/i18n/locales/en.json"
ZH_PATH = ROOT / "src/i18n/locales/zh.json"

# Word-level dictionary
WORDS = {
    "专线": "circuit", "设备": "device", "客户": "tenant", "端口": "port",
    "配置": "config", "告警": "alarm", "流量": "traffic", "带宽": "bandwidth",
    "站点": "site", "厂商": "vendor", "接口": "interface", "隧道": "tunnel",
    "路由": "route", "工单": "work order", "用户": "user", "密码": "password",
    "邮箱": "email", "验证码": "verification code", "登录": "sign in",
    "保存": "save", "删除": "delete", "创建": "create", "编辑": "edit",
    "导出": "export", "导入": "import", "刷新": "refresh", "取消": "cancel",
    "确认": "confirm", "提交": "submit", "开通": "provision", "拆除": "teardown",
    "下发": "push", "学习": "learn", "备份": "backup", "纳管": "onboard",
    "在线": "online", "离线": "offline", "运行": "running", "失败": "failed",
    "成功": "succeeded", "完成": "completed", "执行": "execute", "检测": "probe",
    "拨测": "probe", "时延": "latency", "丢包": "packet loss", "抖动": "jitter",
    "可达": "reachable", "不可达": "unreachable", "健康": "health",
    "阈值": "threshold", "策略": "policy", "权限": "permission",
    "审计": "audit", "通知": "notification", "邮件": "email", "安全": "security",
    "品牌": "brand", "平台": "platform", "设置": "settings", "管理": "management",
    "列表": "list", "详情": "details", "历史": "history", "版本": "version",
    "备注": "notes", "描述": "description", "名称": "name", "编码": "code",
    "类型": "type", "状态": "status", "操作": "actions", "时间": "time",
    "来源": "source", "角色": "role", "凭证": "credentials", "测试": "test",
    "连接": "connection", "会话": "session", "链路": "link", "骨干": "backbone",
    "容量": "capacity", "利用率": "utilization", "峰值": "peak",
    "物理": "physical", "虚拟": "virtual", "主": "primary", "备": "backup",
    "全部": "all", "仅": "only", "暂无": "no", "尚未": "not yet",
    "正在": "in progress", "请": "please", "输入": "enter", "选择": "select",
    "点击": "click", "查看": "view", "添加": "add", "移除": "remove",
    "启用": "enable", "禁用": "disable", "开": "on", "关": "off",
    "可选": "optional", "必填": "required", "默认": "default",
    "国内": "domestic", "国际": "international", "企业": "enterprise",
    "自定义": "custom", "其他": "other", "推荐": "recommended",
    "端口": "port", "采集": "collection", "连通性": "connectivity",
    "现网": "live network", "期望": "desired", "漂移": "drift",
    "业务": "service", "接入": "access", "端点": "endpoint",
    "封装": "encapsulation", "标签": "tag", "限速": "rate limit",
    "占用": "occupancy", "空闲": "idle", "冲突": "conflict",
    "预检": "pre-check", "编排": "orchestration", "回收": "reclaim",
    "模拟": "simulated", "排队": "queued", "回滚": "rolled back",
    "加载": "loading", "发送": "send", "重置": "reset", "找回": "recover",
    "验证": "verify", "绑定": "bind", "解绑": "unbind",
    "至少": "at least", "位": "characters", "条": "items", "个": "",
    "台": "units", "次": "times", "秒": "seconds", "分钟": "minutes",
    "小时": "hours", "天": "days", "周": "weeks", "月": "months",
    "近": "last", "共": "total", "第": "", "至": "to",
    "若": "if", "存在": "exists", "将": "will", "按": "by",
    "后": "after", "前": "before", "内": "within", "外": "external",
    "左": "left", "右": "right", "上": "upper", "下": "lower",
    "新": "new", "旧": "old", "当前": "current", "上次": "last",
    "首次": "first", "全部": "all", "部分": "partial",
    "华为": "Huawei", "华三": "H3C", "思科": "Cisco", "瞻博": "Juniper",
    "二层": "L2", "三层": "L3", "公网": "public", "管理网": "management",
    "出口": "egress", "国家": "country", "地区": "region",
    "自动": "auto", "显式": "explicit", "路径": "path", "经由": "via",
    "合同": "committed", "评分": "score", "跨": "cross", "域": "domain",
    "互联": "interconnect", "拓扑": "topology", "控制面": "control plane",
    "驱动": "driver", "集成": "integration", "北向": "northbound", "南向": "southbound",
    "巡检": "inspection", "引擎": "engine", "周期": "interval",
    "驾驶舱": "dashboard", "态势": "overview", "洞察": "insights",
    "生命周期": "lifecycle", "异构": "heterogeneous", "分布": "distribution",
    "条目": "entries", "路由表": "routing table", "会话": "session",
    "闪断": "flap", "中断": "outage", "劣化": "degradation", "拥塞": "congestion",
    "超标": "exceeded", "频繁": "frequent", "活跃": "active",
    "恢复": "cleared", "确认": "acknowledged", "草稿": "draft",
    "暂停": "suspended", "终止": "terminated", "退服": "decommissioned",
    "降级": "degraded", "待": "pending", "已": "", "未": "not",
    "无": "no", "有": "has", "是": "yes", "否": "no",
    "或": "or", "和": "and", "与": "and", "的": "", "了": "",
    "在": "in", "从": "from", "到": "to", "为": "as", "用": "use",
    "使用": "use", "需要": "required", "可以": "can", "不能": "cannot",
    "支持": "supports", "不支持": "not supported", "仅支持": "only supports",
    "留空": "leave blank", "留空使用": "leave blank to use",
    "平台默认": "platform default", "一键": "one-click",
    "右上角": "top right", "左侧": "left side", "右侧": "right side",
    "下方": "below", "上方": "above", "此处": "here",
    "数据": "data", "记录": "records", "信息": "info", "提示": "hint",
    "错误": "error", "警告": "warning", "说明": "description",
    "文档": "documentation", "示例": "example", "格式": "format",
    "完整": "full", "简短": "short", "简要": "brief",
    "事务邮件": "transactional email", "云邮件": "cloud email",
    "邮箱服务": "email service", "企业邮": "enterprise mail",
    "无加密": "no encryption", "加密": "encryption", "内网": "internal",
}

PHRASES = [
    (r"^请输入(.+)$", r"Enter \1"),
    (r"^请选择(.+)$", r"Select \1"),
    (r"^请(.+)$", r"Please \1"),
    (r"^暂无(.+)$", r"No \1"),
    (r"^尚未(.+)$", r"Not yet \1"),
    (r"^正在(.+)$", r"\1 in progress"),
    (r"^已(.+)$", r"\1"),
    (r"^未(.+)$", r"Not \1"),
    (r"(.+)失败$", r"\1 failed"),
    (r"(.+)成功$", r"\1 succeeded"),
    (r"(.+)中…$", r"\1…"),
    (r"^共\s*(.+)$", r"Total \1"),
    (r"^第\s*(.+?)条，共\s*(.+)$", r"\1 of \2"),
    (r"^近\s*(\d+)\s*小时$", r"Last \1 hours"),
    (r"^近\s*(\d+)\s*天$", r"Last \1 days"),
    (r"^至少\s*(\d+)\s*位$", r"At least \1 characters"),
    (r"^若账号存在，(.+)$", r"If the account exists, \1"),
    (r"^需要(.+)后重试$", r"\1 required, then retry"),
    (r"^(.+)加载失败$", r"Failed to load \1"),
    (r"^(.+)已保存$", r"\1 saved"),
    (r"^(.+)已删除$", r"\1 deleted"),
    (r"^(.+)已创建.*$", r"\1 created"),
    (r"^留空使用(.+)$", r"Leave blank to use \1"),
    (r"^(.+) · (.+)$", r"\1 · \2"),
    (r"^←\s*(.+)$", r"← \1"),
]


def translate_phrase(zh: str) -> str:
    s = zh.strip()
    for pat, repl in PHRASES:
        m = re.match(pat, s)
        if m:
            parts = [translate_phrase(g) if ZH_RE.search(g) else g.strip() for g in m.groups()]
            try:
                return repl.format(*parts) if "{" in repl else re.sub(pat, repl, s)
            except Exception:
                pass
    # word by word
    result = []
    i = 0
    while i < len(s):
        matched = False
        for length in range(min(8, len(s) - i), 0, -1):
            chunk = s[i : i + length]
            if chunk in WORDS:
                w = WORDS[chunk]
                if w:
                    result.append(w)
                i += length
                matched = True
                break
        if not matched:
            ch = s[i]
            if ch in "，。、；：！？（）【】""''·…—":
                result.append({"，": ", ", "。": ".", "、": ", ", "；": "; ", "：": ": ",
                                 "！": "!", "？": "?", "（": "(", "）": ")", "【": "[", "】": "]",
                                 """: '"', """: '"', "'": "'", "'": "'", "·": " · ", "…": "…", "—": "—"}.get(ch, ch))
            elif ZH_RE.match(ch):
                result.append(ch)  # keep untranslated char
            else:
                result.append(ch)
            i += 1
    out = " ".join(result)
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"\s+([,.:;!?])", r"\1", out)
    # Title case first letter
    if out and out[0].islower():
        out = out[0].upper() + out[1:]
    return out if out and not ZH_RE.search(out) else None


ZH_RE = re.compile(r"[\u4e00-\u9fff]")


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def unflatten(flat):
    root = {}
    for key, val in sorted(flat.items()):
        parts = key.split(".")
        cur = root
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = val
    return root


def main():
    en = json.loads(EN_PATH.read_text(encoding="utf-8"))
    zh = json.loads(ZH_PATH.read_text(encoding="utf-8"))
    en_flat = flatten(en)
    zh_flat = flatten(zh)
    fixed = 0
    for key, val in list(en_flat.items()):
        if not str(val).startswith("[EN]"):
            continue
        zh_val = zh_flat.get(key, "")
        translated = translate_phrase(zh_val)
        if translated and not ZH_RE.search(translated):
            en_flat[key] = translated
            fixed += 1
        else:
            # keep technical mixed strings: transliterate remaining
            en_flat[key] = zh_val  # fallback show chinese in EN mode is bad
            # try stripping [EN] prefix approach - use key slug
            slug = key.replace("auto.", "").replace(".", " ")
            en_flat[key] = translate_phrase(zh_val) or f"({zh_val})"

    EN_PATH.write_text(json.dumps(unflatten(en_flat), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    remaining = sum(1 for v in en_flat.values() if ZH_RE.search(str(v)))
    print(f"Fixed {fixed}, remaining Chinese in EN: {remaining}")


if __name__ == "__main__":
    main()

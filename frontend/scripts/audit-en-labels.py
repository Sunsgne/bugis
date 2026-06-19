#!/usr/bin/env python3
"""Audit and fix Title Case for UI labels in en.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_PATH = ROOT / "src/i18n/locales/en.json"
ZH_PATH = ROOT / "src/i18n/locales/zh.json"

# Namespaces where values should be Title Case (short UI labels)
TITLE_NAMESPACES = (
    "action.",
    "account.",
    "page.",
    "table.",
    "empty.",
    "toast.",
    "nav.",
    "enum.",
    "monitor.",
    "network.",
    "portal.",
    "status.",
)

# Keep lowercase (status values, placeholders, technical)
KEEP_LOWER = {
    "up",
    "down",
    "apikey",
    "name@example.com",
    "postmaster@your-domain",
    "any username",
    "iCloud mailbox",
    "draft",
    "active",
    "online",
    "offline",
}

# Exact EN fixes
EXACT_FIX: dict[str, str] = {
    "a4da7e8d": "Search Link / Equipment / Supplier / Site",
    "bab268d5": "Supplier",
    "198835c4": "Site Routing",
    "923c5302": "Allocated Bandwidth",
    "43718dd2": "Bandwidth Allocation Rate",
    "907cf2f8": "Allocated / Total Capacity",
    "f5c78954": "A-Side",
    "3cd8f630": "Z End",
    "802bd": "Utilization",
    "bbdff9f6": "Utilization",
    "a2e883fa": "Committed Bandwidth",
    "account.fullName": "Display Name",
    "account.saveProfile": "Save Profile",
    "account.title": "Account Settings",
    "action.accountSettings": "Account Settings",
    "action.changePassword": "Change Password",
    "action.createCircuit": "Provision Circuit",
    "action.learnNow": "Learn Now",
    "action.viewAll": "Global View",
    "enum.mgmtIpType.management": "Management Network",
    "enum.mgmtIpType.public": "Public Network",
    "table.noData": "No Data",
    "table.pageSize": "{{n}} / Page",
}

SMALL_WORDS = {
    "a", "an", "the", "and", "or", "for", "to", "of", "in", "on", "at", "by",
    "with", "from", "vs", "via", "per", "·", "/", "-",
}


def title_case_label(s: str) -> str:
    if not s or s in KEEP_LOWER:
        return s
    if s.startswith("{{") or s.startswith("${") or "@" in s and "." in s:
        return s
    if re.search(r"[.!?]$", s.strip()) and len(s.split()) > 4:
        return s  # sentence — don't touch
    words = re.split(r"(\s+|/|·|-)", s)
    out: list[str] = []
    for i, w in enumerate(words):
        if not w or w in SMALL_WORDS or re.match(r"^\s+$", w):
            out.append(w)
            continue
        if w.isupper() or re.match(r"^[A-Z0-9]+(?:\.[A-Z0-9]+)?$", w):
            out.append(w)
            continue
        if w.lower() in KEEP_LOWER:
            out.append(w.lower())
            continue
        out.append(w[:1].upper() + w[1:])
    return "".join(out)


def flat(obj: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, str):
            out[key] = v
        elif isinstance(v, dict):
            out.update(flat(v, key))
    return out


def should_title(key: str, val: str) -> bool:
    if key in EXACT_FIX:
        return True
    if any(key.startswith(ns) for ns in TITLE_NAMESPACES):
        if len(val) > 72 or val.count(" ") > 8:
            return False
        if re.search(r"[.!?]$", val.strip()) and len(val.split()) > 5:
            return False
        return True
    if key.startswith("copy.") or key.startswith("auto."):
        if len(val.split()) <= 5 and not re.search(r"[.!?]$", val.strip()):
            if val and val[0].islower():
                return True
        # short hash labels in copy
        if key.startswith("copy.") and len(val) <= 40 and val[0].islower():
            return True
    return False


def walk_fix(obj: dict, prefix: str = "") -> int:
    n = 0
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            n += walk_fix(v, key)
        elif isinstance(v, str):
            if key in EXACT_FIX:
                if v != EXACT_FIX[key]:
                    obj[k] = EXACT_FIX[key]
                    n += 1
            elif should_title(key, v):
                fixed = title_case_label(v)
                if fixed != v and v.lower() not in KEEP_LOWER:
                    obj[k] = fixed
                    n += 1
    return n


def main() -> None:
    data = json.loads(EN_PATH.read_text(encoding="utf-8"))
    n = walk_fix(data)
    EN_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    zh = flat(json.loads(ZH_PATH.read_text(encoding="utf-8")))
    en = flat(json.loads(EN_PATH.read_text(encoding="utf-8")))
    bad = []
    for zk, zv in zh.items():
        ev = en.get(zk)
        if not ev or ev == zv or not re.search(r"[\u4e00-\u9fff]", zv):
            continue
        if len(ev) <= 48 and ev[0].islower() and ev.lower() not in KEEP_LOWER:
            if "{{" not in ev and "${" not in ev:
                bad.append((zv, ev, zk))
    print(f"Fixed {n} strings in en.json")
    print(f"Remaining lowercase zh-mapped labels: {len(bad)}")
    for z, e, k in bad[:30]:
        print(f"  {z!r} -> {e!r} ({k})")


if __name__ == "__main__":
    main()

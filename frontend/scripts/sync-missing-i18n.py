#!/usr/bin/env python3
"""Add missing zh→en copy entries for tc() strings not yet in locale files."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
ZH_PATH = ROOT / "src/i18n/locales/zh.json"
EN_PATH = ROOT / "src/i18n/locales/en.json"
SRC = ROOT / "src"

ZH_RE = re.compile(r"[\u4e00-\u9fff]")
SKIP_PATHS = ("i18n/locales", "data/smtpPresets.ts", "constants/timezones.ts")


def flatten(d: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = str(v)
    return out


def build_zh_to_en(zh_flat: dict[str, str], en_flat: dict[str, str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for key, zh_val in zh_flat.items():
        en_val = en_flat.get(key)
        if en_val and zh_val and en_val != zh_val and not ZH_RE.search(en_val):
            mapping[zh_val] = en_val
    return mapping


def slug(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:8]


def collect_tc_strings() -> set[str]:
    found: set[str] = set()
    for path in SRC.rglob("*.tsx"):
        if any(s in str(path) for s in SKIP_PATHS):
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"tc\(\s*['\"]([^'\"]+)['\"]", text):
            s = m.group(1)
            if ZH_RE.search(s):
                found.add(s)
    return found


def translate_batch(strings: list[str]) -> dict[str, str]:
    tr = GoogleTranslator(source="zh-CN", target="en")
    out: dict[str, str] = {}
    for i, s in enumerate(strings):
        try:
            out[s] = tr.translate(s)
        except Exception:
            out[s] = s
        if (i + 1) % 20 == 0:
            time.sleep(0.4)
        else:
            time.sleep(0.08)
    return out


def main() -> None:
    zh = json.loads(ZH_PATH.read_text(encoding="utf-8"))
    en = json.loads(EN_PATH.read_text(encoding="utf-8"))
    zh_flat = flatten(zh)
    en_flat = flatten(en)
    mapping = build_zh_to_en(zh_flat, en_flat)

    # Extra dashboard / UI strings used without tc yet
    extras = [
        "已执行 {{count}} 次",
        "周期 {{sec}}s",
        "自学习 {{count}} 台",
        "全域分配率",
        "峰值利用率 {{pct}}%",
        "峰值带宽 Rx {{rx}} / Tx {{tx}} · 合计 {{total}}",
        "合同带宽 {{bw}}",
        "采样时间 {{at}}",
        "当前流量 {{traffic}}",
        "告警阈值 {{pct}}%",
    ]

    needed = sorted(s for s in collect_tc_strings() | set(extras) if s not in mapping)
    print(f"Adding {len(needed)} missing copy entries…")

    zh_copy = zh.setdefault("copy", {})
    en_copy = en.setdefault("copy", {})
    translations = translate_batch(needed)

    for s in needed:
        key = slug(s)
        while key in zh_copy and zh_copy[key] != s:
            key = hashlib.md5(f"{s}{key}".encode()).hexdigest()[:8]
        zh_copy[key] = s
        en_copy[key] = translations[s]

    ZH_PATH.write_text(json.dumps(zh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EN_PATH.write_text(json.dumps(en, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    zh_flat = flatten(zh)
    en_flat = flatten(en)
    mapping = build_zh_to_en(zh_flat, en_flat)
    still = [s for s in collect_tc_strings() if s not in mapping and ZH_RE.search(s)]
    print(f"Done. Still missing: {len(still)}")


if __name__ == "__main__":
    main()

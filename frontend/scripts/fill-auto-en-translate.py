#!/usr/bin/env python3
"""Fill auto.* English entries using Google Translate, preserving template tokens."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
EN_PATH = ROOT / "src/i18n/locales/en.json"
ZH_PATH = ROOT / "src/i18n/locales/zh.json"

CJK = re.compile(r"[\u4e00-\u9fff]")
TOKEN_RE = re.compile(
    r"(\$\{[^}]+\}|\{\{[^}]+\}\}|\{[a-zA-Z_][^}]*\})"
)

# Post-fix broken spacing from MT / prior scripts
FIXUPS = [
    (re.compile(r"\bS\s*N\s*M\s*P\b", re.I), "SNMP"),
    (re.compile(r"\bR\s*I\s*B\b", re.I), "RIB"),
    (re.compile(r"\bV\s*N\s*I\b", re.I), "VNI"),
    (re.compile(r"\bV\s*T\s*E\s*P\b", re.I), "VTEP"),
    (re.compile(r"\bB\s*G\s*P\b", re.I), "BGP"),
    (re.compile(r"\bE\s*V\s*P\s*N\b", re.I), "EVPN"),
    (re.compile(r"\bD\s*C\s*I\b", re.I), "DCI"),
    (re.compile(r"\bN\s*E\s*T\s*C\s*O\s*N\s*F\b", re.I), "NETCONF"),
    (re.compile(r"\bQ\s*o\s*S\b", re.I), "QoS"),
    (re.compile(r"\bS\s*L\s*A\b", re.I), "SLA"),
    (re.compile(r"\bD\s*r\s*y\s*-\s*r\s*u\s*n\b", re.I), "Dry-run"),
    (re.compile(r"\$\s*\{\s*"), "${"),
    (re.compile(r"\s+\?\?\s+"), " ?? "),
    (re.compile(r"\s{2,}"), " "),
]


def protect_tokens(text: str) -> tuple[str, list[str]]:
    tokens: list[str] = []

    def repl(m: re.Match) -> str:
        tokens.append(m.group(0))
        return f"__TOK{len(tokens) - 1}__"

    return TOKEN_RE.sub(repl, text), tokens


def restore_tokens(text: str, tokens: list[str]) -> str:
    for i, tok in enumerate(tokens):
        text = text.replace(f"__TOK{i}__", tok)
    return text


def postprocess(text: str) -> str:
    for pat, repl in FIXUPS:
        text = pat.sub(repl, text)
    return text.strip()


def translate_one(translator: GoogleTranslator, zh: str) -> str:
    protected, tokens = protect_tokens(zh)
    if not CJK.search(protected):
        return zh
    try:
        en = translator.translate(protected)
    except Exception as e:
        print(f"  translate error: {e!r} for {zh[:60]!r}")
        return zh
    en = restore_tokens(en, tokens)
    return postprocess(en)


def main() -> None:
    en = json.loads(EN_PATH.read_text(encoding="utf-8"))
    zh = json.loads(ZH_PATH.read_text(encoding="utf-8"))
    auto_zh: dict[str, str] = zh["auto"]
    auto_en: dict[str, str] = en["auto"]

    todo = [
        k
        for k, z in auto_zh.items()
        if CJK.search(str(auto_en.get(k, ""))) or auto_en.get(k) == z
    ]
    print(f"Translating {len(todo)} auto.* keys…")

    translator = GoogleTranslator(source="zh-CN", target="en")
    done = 0
    for i, key in enumerate(todo):
        z = auto_zh[key]
        auto_en[key] = translate_one(translator, z)
        done += 1
        if done % 25 == 0:
            print(f"  {done}/{len(todo)}")
            time.sleep(0.5)
        elif done % 5 == 0:
            time.sleep(0.15)

    en["auto"] = auto_en
    EN_PATH.write_text(json.dumps(en, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    remaining = sum(1 for v in auto_en.values() if CJK.search(str(v)))
    print(f"Done. Remaining CJK in auto.en: {remaining}")


if __name__ == "__main__":
    main()

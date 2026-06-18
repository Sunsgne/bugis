#!/usr/bin/env python3
"""Safe i18n codemod: JSX text + toast/alert strings only; skip module-level constants."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ZH = re.compile(r"[\u4e00-\u9fff]")
SKIP = ("i18n/locales", "i18n/useTc.ts", "constants/uiCopy.ts", "constants/statusLabels.ts",
        "constants/formOptions.ts", "data/smtpPresets.ts", "constants/timezones.ts")

HOOK = 'import { useTc } from "@/i18n/useTc";\n'
HOOK_LINE = "  const { tc } = useTc();"


def add_hook(text: str) -> str:
    if "useTc()" in text:
        return text
    last = None
    for m in re.finditer(r"^import .+;$", text, re.M):
        last = m
    if last:
        text = text[: last.end()] + "\n" + HOOK + text[last.end() + 1 :]
    else:
        text = HOOK + text
    m = re.search(r"(export default function \w+\([^)]*\)\s*\{)", text)
    if m:
        text = text[: m.end()] + "\n" + HOOK_LINE + text[m.end() :]
    return text


def transform_jsx_text(text: str) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        inner = m.group(1)
        if not ZH.search(inner) or "tc(" in inner or "{" in inner:
            return m.group(0)
        s = inner.strip()
        if not s:
            return m.group(0)
        count += 1
        esc = s.replace("\\", "\\\\").replace("'", "\\'")
        return f">{{tc('{esc}')}}<"

    return re.sub(r">([^<>{}]+)<", repl, text), count


def transform_toast(text: str) -> tuple[str, int]:
    count = 0
    pat = re.compile(r"(toast\.(?:success|error|message|info)|message\.(?:success|error|warning|info))\((['\"])([^'\"]+)\2\)")

    def repl(m: re.Match) -> str:
        nonlocal count
        s = m.group(3)
        if not ZH.search(s):
            return m.group(0)
        count += 1
        esc = s.replace("\\", "\\\\").replace("'", "\\'")
        return f"{m.group(1)}(tc('{esc}'))"

    return pat.sub(repl, text), count


def transform_title_props(text: str) -> tuple[str, int]:
    """title="中文" -> title={tc('中文')} in JSX"""
    count = 0
    pat = re.compile(r'\b(title|label|placeholder|okText|cancelText|description|tooltip)=("|\')([^"\']*)\2')

    def repl(m: re.Match) -> str:
        nonlocal count
        s = m.group(3)
        if not ZH.search(s):
            return m.group(0)
        count += 1
        esc = s.replace("\\", "\\\\").replace("'", "\\'")
        return f"{m.group(1)}={{tc('{esc}')}}"

    return pat.sub(repl, text), count


def process(path: Path) -> int:
    if any(s in str(path) for s in SKIP):
        return 0
    if path.suffix not in (".tsx",):
        return 0
    text = path.read_text(encoding="utf-8")
    if not ZH.search(text):
        return 0
    n = 0
    text, c = transform_jsx_text(text)
    n += c
    text, c = transform_toast(text)
    n += c
    text, c = transform_title_props(text)
    n += c
    if n == 0:
        return 0
    text = add_hook(text)
    path.write_text(text, encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}: {n}")
    return n


def main():
    total = sum(process(p) for p in sorted(SRC.rglob("*.tsx")))
    print("total", total)


if __name__ == "__main__":
    main()

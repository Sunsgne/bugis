#!/usr/bin/env python3
"""Codemod: inject useTc() and wrap Chinese string literals with tc()."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ZH = re.compile(r"[\u4e00-\u9fff]")

SKIP = (
    "i18n/locales/",
    "i18n/useTc.ts",
    "constants/uiCopy.ts",
    "constants/statusLabels.ts",
    "constants/formOptions.ts",
    "data/smtpPresets.ts",
    "constants/timezones.ts",
)

# Files already using structured i18n — still need tc for inline Chinese
HOOK_IMPORT = 'import { useTc } from "@/i18n/useTc";\n'
HOOK_IMPORT_REL = 'import { useTc } from "../i18n/useTc";\n'
HOOK_LINE = "  const { t, tc } = useTc();"


def import_line(path: Path) -> str:
    return HOOK_IMPORT if "@/" in path.read_text(encoding="utf-8") or path.parent.name in (
        "pages", "components", "portal"
    ) else HOOK_IMPORT_REL.replace("../i18n", "../i18n" if "portal" not in str(path) else "../i18n")


def add_hook(text: str) -> str:
    if "useTc()" in text or "const { t, tc }" in text:
        if "const { t, tc }" not in text and "useTc()" in text:
            text = text.replace("const { t } = useTranslation();", HOOK_LINE)
        return text
    # prefer useTc over useTranslation when adding
    if 'from "react-i18next"' in text and "useTranslation" in text:
        text = text.replace(
            'import { useTranslation } from "react-i18next";',
            'import { useTc } from "@/i18n/useTc";',
        )
        text = text.replace("const { t } = useTranslation();", HOOK_LINE)
        text = text.replace("const { t, i18n } = useTranslation();", "  const { t, tc, i18n } = useTc();")
        return text
    imp = HOOK_IMPORT
    last = None
    for m in re.finditer(r"^import .+;$", text, re.M):
        last = m
    if last:
        text = text[: last.end()] + "\n" + imp + text[last.end() + 1 :]
    else:
        text = imp + text
    m = re.search(r"(export default function \w+\([^)]*\)\s*\{)", text)
    if not m:
        m = re.search(r"(export function \w+\([^)]*\)\s*\{)", text)
    if m:
        text = text[: m.end()] + "\n" + HOOK_LINE + text[m.end() :]
    return text


def escape_sq(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def transform(text: str) -> tuple[str, int]:
    count = 0

    def wrap_tc(s: str, quote: str) -> str:
        nonlocal count
        if not ZH.search(s):
            return f"{quote}{s}{quote}"
        if "{{" in s or "${" in s or "`" in s:
            return f"{quote}{s}{quote}"
        count += 1
        return f"{{tc('{escape_sq(s)}')}}"

    # JSX text nodes: >中文<
    def jsx_text(m: re.Match) -> str:
        nonlocal count
        inner = m.group(1)
        if not ZH.search(inner) or inner.strip() == "":
            return m.group(0)
        count += 1
        return f">{{tc('{escape_sq(inner.strip())}')}}<"

    text = re.sub(r">([^<>{}]+)<", jsx_text, text)

    # String literals in common positions
    def str_lit(m: re.Match) -> str:
        q, s = m.group(1), m.group(2)
        if not ZH.search(s):
            return m.group(0)
        # skip import paths and already wrapped
        if s.startswith(".") or s.startswith("/"):
            return m.group(0)
        return wrap_tc(s, q)

    text = re.sub(r'(["\'])([^"\'\\]*(?:\\.[^"\'\\]*)*)\1', str_lit, text)

    return text, count


def process(path: Path) -> int:
    rel = str(path.relative_to(ROOT))
    if any(s in rel for s in SKIP):
        return 0
    raw = path.read_text(encoding="utf-8")
    if not ZH.search(raw):
        return 0
    text, n = transform(raw)
    if n == 0:
        return 0
    if "export default function" in text or "export function" in text:
        text = add_hook(text)
    path.write_text(text, encoding="utf-8")
    print(f"  {rel}: {n}")
    return n


def main():
    total = 0
    for p in sorted(SRC.rglob("*")):
        if p.suffix in (".tsx", ".ts"):
            total += process(p)
    print(f"total {total}")


if __name__ == "__main__":
    main()

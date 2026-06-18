#!/usr/bin/env python3
"""Replace Chinese string literals with t('key') in React source files."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MAP_PATH = ROOT / "scripts/i18n-string-map.json"

ZH_RE = re.compile(r"[\u4e00-\u9fff]")
# Match simple string literals containing Chinese (no nested quotes)
LIT = re.compile(r'(["\'`])([^"\'`\\]*(?:\\.[^"\'`\\]*)*)\1')

SKIP_FILES = {
    "i18n/locales/zh.json",
    "i18n/locales/en.json",
    "constants/uiCopy.ts",  # deprecated shim
    "constants/statusLabels.ts",
    "constants/formOptions.ts",
}


def needs_hook(text: str) -> bool:
    return bool(re.search(r"\bt\(", text)) is False and ZH_RE.search(text) is not None


def ensure_imports(text: str) -> str:
    if "useTranslation" in text:
        return text
    if not re.search(r"export default function|export function \w+\(", text):
        return text
    # add import after last import
    imp = 'import { useTranslation } from "react-i18next";\n'
    if imp.strip() in text:
        return text
    last_import = None
    for m in re.finditer(r"^import .+;$", text, re.M):
        last_import = m
    if last_import:
        pos = last_import.end()
        text = text[:pos] + "\n" + imp + text[pos:]
    else:
        text = imp + text
    return text


def ensure_hook(text: str) -> str:
    if "const { t } = useTranslation()" in text or "const {t} = useTranslation()" in text:
        return text
    # insert after first line of default export function
    m = re.search(r"(export default function \w+\([^)]*\)\s*\{)", text)
    if not m:
        m = re.search(r"(export function \w+\([^)]*\)\s*\{)", text)
    if not m:
        return text
    insert_at = m.end()
    return text[:insert_at] + "\n  const { t } = useTranslation();" + text[insert_at:]


def replace_literals(text: str, mapping: dict[str, str]) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        quote, inner = m.group(1), m.group(2)
        if not ZH_RE.search(inner):
            return m.group(0)
        if inner in mapping:
            count += 1
            return f"{{t('{mapping[inner]}')}}"
        return m.group(0)

    # JSX attribute values: title="中文" -> title={t('key')}
    def attr_repl(m: re.Match) -> str:
        nonlocal count
        attr, quote, inner = m.group(1), m.group(2), m.group(3)
        if not ZH_RE.search(inner) or inner not in mapping:
            return m.group(0)
        count += 1
        return f"{attr}={{t('{mapping[inner]}')}}"

    text = re.sub(r"(\w+)=([\"'])([^\"']*)\2", attr_repl, text)
    # toast/message calls
    text = re.sub(
        r"(toast\.(?:success|error|message|info))\(([\"'])([^\"']*)\2\)",
        lambda m: f"{m.group(1)}(t('{mapping[m.group(3)]}'))" if m.group(3) in mapping and ZH_RE.search(m.group(3)) else m.group(0),
        text,
    )
    return text, count


def process_file(path: Path, mapping: dict[str, str]) -> int:
    rel = str(path.relative_to(ROOT))
    if any(s in rel for s in SKIP_FILES):
        return 0
    text = path.read_text(encoding="utf-8")
    if not ZH_RE.search(text):
        return 0
    new_text, count = replace_literals(text, mapping)
    if count == 0:
        return 0
    if needs_hook(new_text):
        new_text = ensure_imports(new_text)
        new_text = ensure_hook(new_text)
    path.write_text(new_text, encoding="utf-8")
    print(f"  {rel}: {count} replacements")
    return count


def main():
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    total = 0
    for p in sorted(SRC.rglob("*")):
        if p.suffix not in (".tsx", ".ts"):
            continue
        if "i18n/locales" in str(p):
            continue
        total += process_file(p, mapping)
    print(f"Total replacements: {total}")


if __name__ == "__main__":
    main()

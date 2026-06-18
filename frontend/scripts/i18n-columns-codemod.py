#!/usr/bin/env python3
"""Translate title/label string props inside component bodies (indented lines)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH = re.compile(r"[\u4e00-\u9fff]")
SKIP = ("i18n/", "constants/", "data/")

HOOK = 'import { useTc } from "@/i18n/useTc";\n'
HOOK_LINE = "  const { tc } = useTc();"


def ensure_hook(text: str) -> str:
    if "useTc()" in text:
        return text
    last = None
    for m in re.finditer(r"^import .+;$", text, re.M):
        last = m
    if last:
        text = text[: last.end()] + "\n" + HOOK + text[last.end() + 1 :]
    m = re.search(r"(export default function \w+\([^)]*\)\s*\{)", text)
    if m:
        text = text[: m.end()] + "\n" + HOOK_LINE + text[m.end() :]
    return text


def process(path: Path) -> int:
    if path.suffix not in (".tsx",):
        return 0
    if any(s in str(path) for s in SKIP):
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    count = 0
    out = []
    pat = re.compile(r"^(\s{4,})(title|label|placeholder|message|okText|cancelText|description|tooltip|emptyText):\s*(['\"])([^'\"]+)\3\s*,?\s*$")
    for line in lines:
        m = pat.match(line)
        if m and ZH.search(m.group(4)) and "tc(" not in line:
            indent, key, q, val = m.group(1), m.group(2), m.group(3), m.group(4)
            esc = val.replace("\\", "\\\\").replace("'", "\\'")
            out.append(f"{indent}{key}: tc('{esc}'),")
            count += 1
        else:
            out.append(line)
    if count:
        text = ensure_hook("\n".join(out) + "\n")
        path.write_text(text, encoding="utf-8")
        print(f"  {path.relative_to(ROOT)}: {count}")
    return count


def main():
    total = sum(process(p) for p in sorted((ROOT / "src").rglob("*.tsx")))
    print("total", total)


if __name__ == "__main__":
    main()

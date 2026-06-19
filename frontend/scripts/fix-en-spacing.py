#!/usr/bin/env python3
"""Repair corrupted English locale strings (spaced acronyms, broken ${...} tokens)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_PATH = ROOT / "src/i18n/locales/en.json"

ACRONYM_FIXUPS = [
    (re.compile(r"\bS\s*N\s*M\s*P\b", re.I), "SNMP"),
    (re.compile(r"\bR\s*I\s*B\b", re.I), "RIB"),
    (re.compile(r"\bV\s*N\s*I\b", re.I), "VNI"),
    (re.compile(r"\bV\s*T\s*E\s*P\b", re.I), "VTEP"),
    (re.compile(r"\bB\s*G\s*P\b", re.I), "BGP"),
    (re.compile(r"\bE\s*V\s*P\s*N\b", re.I), "EVPN"),
    (re.compile(r"\bD\s*C\s*I\b", re.I), "DCI"),
    (re.compile(r"\bN\s*E\s*T\s*C\s*O\s*N\s*F\b", re.I), "NETCONF"),
    (re.compile(r"\bS\s*S\s*H\b", re.I), "SSH"),
    (re.compile(r"\bS\s*L\s*A\b", re.I), "SLA"),
    (re.compile(r"\bM\s*P\s*L\s*S\b", re.I), "MPLS"),
    (re.compile(r"\bS\s*-\s*V\s*-\s*I\s*D\b", re.I), "S-VID"),
    (re.compile(r"\bS\s*T\s*A\s*R\s*T\s*T\s*L\s*S\b", re.I), "STARTTLS"),
    (re.compile(r"\bS\s*S\s*L\s*/\s*T\s*L\s*S\b", re.I), "SSL/TLS"),
    (re.compile(r"\bI\s*G\s*P\b", re.I), "IGP"),
    (re.compile(r"\bM\s*F\s*A\b", re.I), "MFA"),
    (re.compile(r"\bU\s*D\s*P\b", re.I), "UDP"),
    (re.compile(r"\bI\s*P\b"), "IP"),
    (re.compile(r"\bI\s*D\b"), "ID"),
    (re.compile(r"\bE\s*S\s*P\b", re.I), "ESP"),
    (re.compile(r"\bA\s*N\s*S\s*I\b", re.I), "ANSI"),
    (re.compile(r"\bQ\s*o\s*S\b", re.I), "QoS"),
    (re.compile(r"\bD\s*r\s*y\s*-\s*r\s*u\s*n\b", re.I), "Dry-run"),
    (re.compile(r"\bE\s*n\s*a\s*b\s*l\s*e\b", re.I), "Enable"),
    (re.compile(r"\bN\s*e\s*t\s*m\s*i\s*k\s*o\b", re.I), "Netmiko"),
    (re.compile(r"\bM\s*a\s*n\s*d\s*r\s*i\s*l\s*l\b", re.I), "Mandrill"),
    (re.compile(r"\bM\s*a\s*i\s*l\s*j\s*e\s*t\b", re.I), "Mailjet"),
    (re.compile(r"\bZ\s*o\s*h\s*o\s*M\s*a\s*i\s*l\b", re.I), "Zoho Mail"),
    (re.compile(r"\bS\s*e\s*e\s*r\s*E\s*n\s*g\s*i\s*n\s*e\b", re.I), "SeerEngine"),
    (re.compile(r"\bW\s*e\s*b\s*h\s*o\s*o\s*k\b", re.I), "Webhook"),
    (re.compile(r"\bS\s*t\s*a\s*c\s*k\s*S\s*t\s*o\s*r\s*m\b", re.I), "StackStorm"),
    (re.compile(r"\bI\s*T\s*S\s*M\b", re.I), "ITSM"),
    (re.compile(r"\bI\s*C\s*l\s*o\s*u\s*d\b", re.I), "iCloud"),
    (re.compile(r"\bA\s*n\s*s\s*i\s*b\s*l\s*e\b", re.I), "Ansible"),
    (re.compile(r"\bL\s*o\s*g\s*o\b", re.I), "Logo"),
    (re.compile(r"\bD\s*e\s*s\s*i\s*r\s*e\s*d\b", re.I), "Desired"),
    (re.compile(r"\bW\s*a\s*r\s*n\s*i\s*n\s*g\b", re.I), "Warning"),
    (re.compile(r"\bI\s*n\s*f\s*o\b", re.I), "Info"),
    (re.compile(r"\bM\s*b\s*p\s*s\b", re.I), "Mbps"),
    (re.compile(r"\bN\s*C\s*E\s*-\s*F\s*a\s*b\s*r\s*i\s*c\b", re.I), "NCE-Fabric"),
    (re.compile(r"\bQ\s*Q\b", re.I), "QQ"),
    (re.compile(r"\bS\s*R\b"), "SR"),
    (re.compile(r"\bP\s*E\b"), "PE"),
    (re.compile(r"\bu\s*p\b", re.I), "up"),
    (re.compile(r"\$\s*\{\s*"), "${"),
    (re.compile(r"\s+\?\?\s+"), " ?? "),
]

# Collapse words spelled with spaces between letters: "F a b r i c" -> "Fabric"
SPACED_WORD = re.compile(
    r"(?<![A-Za-z0-9])((?:[A-Za-z] ){2,}[A-Za-z])(?![A-Za-z0-9])"
)


def collapse_spaced_words(text: str) -> str:
    def repl(m: re.Match) -> str:
        raw = m.group(1)
        collapsed = raw.replace(" ", "")
        # Only collapse if it looks like a corrupted word (3+ letters)
        if len(collapsed) >= 3 and collapsed.isalpha():
            return collapsed
        return raw

    return SPACED_WORD.sub(repl, text)


HTML_TAG_FIXUPS = [
    (re.compile(r"<\s*b\s+r\s*/?\s*>", re.I), "<br/>"),
    (re.compile(r"<\s*b\s*>", re.I), "<b>"),
    (re.compile(r"<\s*/\s*b\s*>", re.I), "</b>"),
    (re.compile(r"\(\s*m\s*s\s*\)", re.I), "(ms)"),
    (re.compile(r"\(\s*M\s*b\s*p\s*s\s*\)", re.I), "(Mbps)"),
]


def collapse_digit_runs(text: str) -> str:
    def repl(m: re.Match) -> str:
        return re.sub(r"\s+", "", m.group(0))

    return DIGIT_RUN.sub(repl, text)


def collapse_template_inner(inner: str) -> str:
    """Collapse spaces between identifier characters inside a template expression."""
    prev = None
    cur = inner
    while prev != cur:
        prev = cur
        cur = re.sub(r"(?<=[\w.$\[\]|?:'\"]) +(?=[\w.$\[\]|?:'\"])", "", cur)
    return cur.strip()


def fix_template_body(body: str) -> str:
    """Remove spaces between identifier characters inside ${...}."""
    out: list[str] = []
    i = 0
    while i < len(body):
        if body[i : i + 2] == "${":
            j = body.find("}", i)
            if j == -1:
                out.append(body[i:])
                break
            inner = collapse_template_inner(body[i + 2 : j])
            out.append("${" + inner + "}")
            i = j + 1
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def fix_string(val: str) -> str:
    if not isinstance(val, str):
        return val
    s = fix_template_body(val)
    for pat, repl in ACRONYM_FIXUPS:
        s = pat.sub(repl, s)
    for pat, repl in HTML_TAG_FIXUPS:
        s = pat.sub(repl, s)
    s = collapse_spaced_words(s)
    s = collapse_digit_runs(s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+([,.:;!?])", r"\1", s)
    return s.strip()


# Fix digits split by spaces inside port numbers etc.: "5 87" -> "587"
DIGIT_RUN = re.compile(r"(?<!\d)(?:\d(?:\s+\d)+)(?!\d)")


def walk(obj):
    if isinstance(obj, dict):
        return {k: walk(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk(v) for v in obj]
    if isinstance(obj, str):
        return fix_string(obj)
    return obj


def main() -> None:
    data = json.loads(EN_PATH.read_text(encoding="utf-8"))
    fixed = walk(data)
    EN_PATH.write_text(json.dumps(fixed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Report remaining suspicious patterns
    flat = json.dumps(fixed)
    spaced = len(re.findall(r"[A-Za-z] [A-Za-z] [A-Za-z]", flat))
    broken = len(re.findall(r"\$\s+\{", flat))
    print(f"Wrote {EN_PATH.name}; remaining spaced-letter runs ~{spaced}, broken ${{ ~{broken}")


if __name__ == "__main__":
    main()

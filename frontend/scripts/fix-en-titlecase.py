#!/usr/bin/env python3
"""Title-case UI labels and fix known broken English strings in en.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_PATH = ROOT / "src/i18n/locales/en.json"

# Exact value replacements (zh key -> new EN)
EXACT: dict[str, str] = {
    "923c5302": "Allocated Bandwidth",
    "43718dd2": "Bandwidth Allocation Rate",
    "907cf2f8": "Allocated / Total Capacity",
    "bab268d5": "Supplier",
    "198835c4": "Site Routing",
    "6395155f": "There are currently no active circuits. Please go to",
    "21059001": "to create and activate a circuit, or click Refresh to try again.",
    "dfb3d95c": "For device config, see",
    "54c115f7": "No monitorable circuits",
    "470585dc": "Average Delay",
    "f11eb4b0": "Health Index",
    "5c089d82": "Latency / Jitter",
    "4e5cbcb5": "Configuration Delivery / Initialization",
    "2cb472ff": "Initialization",
    "655b4eb2": "S-VID (Platform)",
    "0a705162": "S-VID (Manual)",
    "63204f15": "S-VID (Device)",
    "2a127359": "Legend:",
    "87bb5bbc": "Idle",
    "cd649f76": "Time Range",
    "0cb185b3": "All (${vniIndex.length})",
    "d0a356d0": "SNMP collected ${data.collected} items${data.skipped ? `, ${data.skipped} skipped` : ''}",
    "cfb75a72": "Platform default: ${platformDefault} ms",
    "200607fc": "Progress popup",
    "66241851": "Bugis is the platform's built-in SDN controller.",
    "a3098ebb": "SNMP community: configure in Management settings.",
    "df7fafc9": "No SNMP data yet. Click SNMP Discovery on the right.",
    "bec24f6d": "Routing Mode",
    "02c92bca": "Status Filter",
    "0fb9614a": "Recent Results",
    "1d468be9": "End Date",
    "b44c0f33": "Start Date",
    "23dc1779": "Associated Controller",
    "3c81db28": "Data Center",
    "8901809f": "Background Scheduler",
    "599b5a32": "Total",
    "85541bd9": "Read Only",
    "75c65777": "Global Brand",
    "5b48dbb8": "Check the Details",
    "c6e3373a": "Flow",
    "e366ccf1": "Set Up",
    "64ca9bab": "Reload",
    "4b9c3271": "Reset",
    "42ac9be9": "Sampling",
    "ac341bea": "Controller",
    "0a60ac8f": "Yes",
    "8048909f": "Forgot Password?",
}

# Title-case short UI labels (no sentence punctuation, <= 5 words)
SKIP_TITLE = re.compile(r"[.!?]|^\$\{|^<|^http", re.I)


def title_case_label(s: str) -> str:
    if SKIP_TITLE.search(s) or len(s) > 64:
        return s
    words = s.split()
    if len(words) > 6:
        return s
    out = []
    for w in words:
        if w in {"/", "·", "-", "(", ")", "≥", "≤", "<", ">", "&"}:
            out.append(w)
        elif w.isupper() or re.match(r"^[A-Z0-9/-]+$", w):
            out.append(w)
        elif "/" in w:
            out.append("/".join(p[:1].upper() + p[1:] if p else p for p in w.split("/")))
        else:
            out.append(w[:1].upper() + w[1:] if w else w)
    return " ".join(out)


def walk(obj, path: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_path = f"{path}.{k}" if path else k
            if k in EXACT and isinstance(v, str):
                obj[k] = EXACT[k]
            elif isinstance(v, str) and ("auto" in key_path or "copy" in key_path or key_path.startswith("z_")):
                if k not in EXACT:
                    obj[k] = title_case_label(v)
            else:
                walk(v, key_path)
    elif isinstance(obj, list):
        for item in obj:
            walk(item, path)


def main() -> None:
    data = json.loads(EN_PATH.read_text(encoding="utf-8"))
    walk(data)
    EN_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {EN_PATH.name}")


if __name__ == "__main__":
    main()

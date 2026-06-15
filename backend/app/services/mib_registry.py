"""Symbolic OIDs for bundled IETF MIBs (see backend/mibs/).

Sources synced from net-snmp master (RFC 2863 IF-MIB, SNMPv2-SMI/TC, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MIB_ROOT = Path(__file__).resolve().parents[2] / "mibs"


@dataclass(frozen=True, slots=True)
class MibOid:
    """Human-readable OID with MIB provenance."""

    symbol: str
    oid: str
    mib: str
    rfc: str = ""

    def column(self, index: int) -> str:
        return f"{self.oid}.{index}"


class IF_MIB:
    """RFC 2863 — The Interfaces Group MIB (IF-MIB.txt)."""

    RFC = "RFC2863"
    MIB = "IF-MIB"

    # ifTable
    ifIndex = MibOid("ifIndex", "1.3.6.1.2.1.2.2.1.1", MIB, RFC)
    ifDescr = MibOid("ifDescr", "1.3.6.1.2.1.2.2.1.2", MIB, RFC)
    ifType = MibOid("ifType", "1.3.6.1.2.1.2.2.1.3", MIB, RFC)
    ifSpeed = MibOid("ifSpeed", "1.3.6.1.2.1.2.2.1.5", MIB, RFC)
    ifPhysAddress = MibOid("ifPhysAddress", "1.3.6.1.2.1.2.2.1.6", MIB, RFC)
    ifAdminStatus = MibOid("ifAdminStatus", "1.3.6.1.2.1.2.2.1.7", MIB, RFC)
    ifOperStatus = MibOid("ifOperStatus", "1.3.6.1.2.1.2.2.1.8", MIB, RFC)
    ifLastChange = MibOid("ifLastChange", "1.3.6.1.2.1.2.2.1.9", MIB, RFC)
    ifInOctets = MibOid("ifInOctets", "1.3.6.1.2.1.2.2.1.10", MIB, RFC)
    ifOutOctets = MibOid("ifOutOctets", "1.3.6.1.2.1.2.2.1.16", MIB, RFC)
    ifInErrors = MibOid("ifInErrors", "1.3.6.1.2.1.2.2.1.14", MIB, RFC)
    ifOutErrors = MibOid("ifOutErrors", "1.3.6.1.2.1.2.2.1.20", MIB, RFC)

    # ifXTable (ifMIBObjects 1)
    ifName = MibOid("ifName", "1.3.6.1.2.1.31.1.1.1.1", MIB, RFC)
    ifInMulticastPkts = MibOid("ifInMulticastPkts", "1.3.6.1.2.1.31.1.1.1.2", MIB, RFC)
    ifInBroadcastPkts = MibOid("ifInBroadcastPkts", "1.3.6.1.2.1.31.1.1.1.3", MIB, RFC)
    ifOutMulticastPkts = MibOid("ifOutMulticastPkts", "1.3.6.1.2.1.31.1.1.1.4", MIB, RFC)
    ifOutBroadcastPkts = MibOid("ifOutBroadcastPkts", "1.3.6.1.2.1.31.1.1.1.5", MIB, RFC)
    ifHCInOctets = MibOid("ifHCInOctets", "1.3.6.1.2.1.31.1.1.1.6", MIB, RFC)
    ifHCInUcastPkts = MibOid("ifHCInUcastPkts", "1.3.6.1.2.1.31.1.1.1.7", MIB, RFC)
    ifHCInMulticastPkts = MibOid("ifHCInMulticastPkts", "1.3.6.1.2.1.31.1.1.1.8", MIB, RFC)
    ifHCInBroadcastPkts = MibOid("ifHCInBroadcastPkts", "1.3.6.1.2.1.31.1.1.1.9", MIB, RFC)
    ifHCOutOctets = MibOid("ifHCOutOctets", "1.3.6.1.2.1.31.1.1.1.10", MIB, RFC)
    ifHCOutUcastPkts = MibOid("ifHCOutUcastPkts", "1.3.6.1.2.1.31.1.1.1.11", MIB, RFC)
    ifHCOutMulticastPkts = MibOid("ifHCOutMulticastPkts", "1.3.6.1.2.1.31.1.1.1.12", MIB, RFC)
    ifHCOutBroadcastPkts = MibOid("ifHCOutBroadcastPkts", "1.3.6.1.2.1.31.1.1.1.13", MIB, RFC)
    ifLinkUpDownTrapEnable = MibOid("ifLinkUpDownTrapEnable", "1.3.6.1.2.1.31.1.1.1.14", MIB, RFC)
    ifHighSpeed = MibOid("ifHighSpeed", "1.3.6.1.2.1.31.1.1.1.15", MIB, RFC)
    ifPromiscuousMode = MibOid("ifPromiscuousMode", "1.3.6.1.2.1.31.1.1.1.16", MIB, RFC)
    ifConnectorPresent = MibOid("ifConnectorPresent", "1.3.6.1.2.1.31.1.1.1.17", MIB, RFC)
    ifAlias = MibOid("ifAlias", "1.3.6.1.2.1.31.1.1.1.18", MIB, RFC)
    ifCounterDiscontinuityTime = MibOid(
        "ifCounterDiscontinuityTime", "1.3.6.1.2.1.31.1.1.1.19", MIB, RFC
    )


# ifOperStatus enumerations (IF-MIB)
IF_OPER_STATUS: dict[int, str] = {
    1: "up",
    2: "down",
    3: "testing",
    4: "unknown",
    5: "dormant",
    6: "notPresent",
    7: "lowerLayerDown",
}


def list_bundled_mibs() -> list[dict]:
    """Return metadata for MIB text files shipped under backend/mibs/."""
    manifest_path = MIB_ROOT / "MANIFEST.json"
    if manifest_path.is_file():
        import json

        return json.loads(manifest_path.read_text(encoding="utf-8")).get("mibs", [])

    out: list[dict] = []
    for path in sorted(MIB_ROOT.rglob("*.txt")):
        rel = path.relative_to(MIB_ROOT)
        out.append({"file": str(rel), "mib": path.stem})
    return out

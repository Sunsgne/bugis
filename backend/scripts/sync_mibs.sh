#!/usr/bin/env bash
# Sync IETF MIB text files from net-snmp (upstream reference implementation).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIBDIR="$ROOT/mibs/ietf"
BASE="https://raw.githubusercontent.com/net-snmp/net-snmp/master/mibs"

MIBS=(
  SNMPv2-SMI.txt
  SNMPv2-TC.txt
  SNMPv2-MIB.txt
  INET-ADDRESS-MIB.txt
  IF-MIB.txt
  IF-INVERTED-STACK-MIB.txt
  IANAifType-MIB.txt
)

mkdir -p "$MIBDIR"
for f in "${MIBS[@]}"; do
  echo ">> $f"
  curl -fsSL -o "$MIBDIR/$f" "$BASE/$f"
done

echo "Done. Update mibs/MANIFEST.json updated date if OIDs changed."

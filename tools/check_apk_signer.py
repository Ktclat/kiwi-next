#!/usr/bin/env python3
"""Check one apksigner-reported certificate against the pinned dev certificate."""

import re
import sys
from pathlib import Path

EXPECTED_SIGNER = "32a2fc74d731105859e5a85df16d95f102d85b22099b8064c5d8915c61dad1e0"


def report_matches(text: str) -> bool:
    rows = re.findall(
        r"(?m)^\s*Signer #([0-9]+) certificate SHA-256 digest:\s*([^\r\n]+)$",
        text,
    )
    if len(rows) != 1 or rows[0][0] != "1":
        return False
    digest = rows[0][1].strip()
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{64}|[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){31})", digest):
        return False
    return digest.replace(":", "").lower() == EXPECTED_SIGNER


if __name__ == "__main__":
    if sys.argv[1:] == ["--expected"]:
        print(EXPECTED_SIGNER)
        raise SystemExit(0)
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_apk_signer.py APKSIGNER_LOG | --expected")
    if not report_matches(Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")):
        print(f"Expected exactly one signer with pinned SHA-256 {EXPECTED_SIGNER}.", file=sys.stderr)
        raise SystemExit(1)
    print(f"APK signer matches the pinned engineering certificate: {EXPECTED_SIGNER}")

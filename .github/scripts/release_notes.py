#!/usr/bin/env python3
"""Print the CHANGELOG.md section for a version (0.1.1 or v0.1.1).

Exits non-zero when the section is missing or empty, so a release cannot be
published without notes. Used by the release workflow and for manual releases.
"""
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[2] / "CHANGELOG.md"


def section(version: str, text: str) -> str:
    match = re.search(rf"^## {re.escape(version)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match or not match.group(1).strip():
        raise SystemExit(f"CHANGELOG.md has no notes for {version}")
    return match.group(1).strip() + "\n"


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"v?[0-9]+\.[0-9]+\.[0-9]+", sys.argv[1]):
        raise SystemExit("usage: release_notes.py [v]X.Y.Z")
    sys.stdout.write(section(sys.argv[1].removeprefix("v"), CHANGELOG.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()

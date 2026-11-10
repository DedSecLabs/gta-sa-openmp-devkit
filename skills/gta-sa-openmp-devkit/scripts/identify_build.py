#!/usr/bin/env python3
"""Identify a GTA San Andreas executable from its bytes, never from its file or folder name.

Read-only. Prints JSON: size, SHA-256, PE header facts, optional byte probes, and the comparison with
assets/known-builds.json. A hash match means "same file as a build someone recorded"; the label keeps the
confidence recorded for that build.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep the installed skill folder unchanged

import argparse
import json
import os
from pathlib import Path

from _common import (DevkitError, TOOL_VERSION, parse_hex, probe, read_json, read_pe, run, sha256_file)

DEFAULT_TABLE = Path(__file__).resolve().parent.parent / "assets" / "known-builds.json"


def identify(exe, table_path=DEFAULT_TABLE, extra_probes=(), probe_length=16, show_bytes=False) -> dict:
    exe = Path(exe)
    if not exe.is_file():
        raise DevkitError("executable not found: %s" % exe)
    table = read_json(table_path)
    builds = table.get("builds", []) if isinstance(table, dict) else []
    result = {"schemaVersion": 1, "tool": "identify_build.py " + TOOL_VERSION,
              "file": {"size": os.path.getsize(exe), "sha256": sha256_file(exe)}}
    pe = read_pe(exe)
    result["pe"] = pe
    result["probes"] = []
    if pe.get("valid"):
        for text in extra_probes:
            result["probes"].append(probe(exe, pe, parse_hex(text), probe_length, show_bytes))

    hash_match = next((b for b in builds if b.get("exe", {}).get("sha256") == result["file"]["sha256"]), None)
    signature_matches = []
    if pe.get("valid") and hash_match is None:
        for build in builds:
            checks = build.get("probes") or []
            if not checks:
                continue
            got = [probe(exe, pe, parse_hex(c["va"]), int(c["length"])) for c in checks]
            if all(g["sha256"] == c["sha256"] for g, c in zip(got, checks)):
                signature_matches.append({"id": build.get("id"), "label": build.get("label"),
                                          "probesMatched": len(checks)})
    if hash_match is not None:
        identity = {"match": "hash", "id": hash_match.get("id"), "label": hash_match.get("label"),
                    "labelConfidence": hash_match.get("labelConfidence", "documented-only"),
                    "meaning": "Byte-identical to a recorded executable. The label is only as strong as labelConfidence."}
    elif signature_matches:
        identity = {"match": "probes-only", "candidates": signature_matches, "labelConfidence": "documented-only",
                    "meaning": "Not a recorded file. Some byte signatures match; this shows layout compatibility at "
                               "those addresses only. Re-confirm every address before use."}
    else:
        identity = {"match": "none", "labelConfidence": None,
                    "meaning": "Unknown executable. Treat any version label as documented-only and do not reuse "
                               "addresses from other builds without checking bytes."}
    result["identity"] = identity
    result["knownBuildsTable"] = {"path": str(table_path), "entries": len(builds)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("exe", help="path to the executable (read-only)")
    parser.add_argument("--known-builds", default=str(DEFAULT_TABLE), help="alternative known-builds table")
    parser.add_argument("--probe", action="append", default=[], metavar="VA",
                        help="hash PROBE_LENGTH on-disk bytes at this virtual address (repeatable)")
    parser.add_argument("--probe-length", type=int, default=16)
    parser.add_argument("--show-bytes", action="store_true", help="also print probe bytes (keep them out of documents)")
    args = parser.parse_args()
    if not 1 <= args.probe_length <= 64:
        raise DevkitError("--probe-length must be between 1 and 64")
    print(json.dumps(identify(args.exe, args.known_builds, args.probe, args.probe_length, args.show_bytes), indent=1))


if __name__ == "__main__":
    run(main)

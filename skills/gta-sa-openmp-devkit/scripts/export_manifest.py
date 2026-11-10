#!/usr/bin/env python3
"""Record what a GTA San Andreas installation contains, as metadata only.

Read-only: never starts the game, never writes inside the installation, copies no game content. Emits sizes,
SHA-256 hashes, PE header facts and, optionally, a comparison with hashes you recorded earlier (--reference).
Matching an earlier hash shows consistency with that earlier export; it does not prove a pristine original.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep the installed skill folder unchanged

import argparse
import datetime
import os
import platform

from _common import (TOOL_VERSION, ci_path, game_root, is_sha256, read_json, read_pe, rel_posix, run,
                     sha256_bytes, sha256_file, utc_now, write_json, EXE_NAMES)

GROUPS = [  # id, pattern, directory parts, suffix, recursive
    ("script", "data/script/*", ("data", "script"), "", True),
    ("maps-ipl", "data/maps/**/*.ipl", ("data", "maps"), ".ipl", True),
    ("maps-ide", "data/maps/**/*.ide", ("data", "maps"), ".ide", True),
    ("data-dat", "data/*.dat", ("data",), ".dat", False),
    ("data-cfg", "data/*.cfg", ("data",), ".cfg", False),
    ("data-ide", "data/*.ide", ("data",), ".ide", False),
    ("data-zon", "data/*.zon", ("data",), ".zon", False),
    ("text", "text/*.gxt", ("text",), ".gxt", False),
    ("archives", "models/*.img", ("models",), ".img", False),
]


def load_references(paths) -> dict:
    """Collect path -> sha256 from any JSON shape: flat maps, {path, sha256} objects, earlier manifests."""
    recorded = {}

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("path"), str) and is_sha256(node.get("sha256")):
                recorded[node["path"].replace("\\", "/").lower()] = node["sha256"].lower()
            for key, value in node.items():
                if isinstance(value, str) and is_sha256(value) and ("/" in key or "\\" in key or "." in key):
                    recorded[key.replace("\\", "/").lower()] = value.lower()
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for path in paths:
        walk(read_json(path))
    return recorded


def build_manifest(game_dir, references=(), hash_archives=False, aggregate_only=False, label=None) -> dict:
    root = game_root(game_dir)
    recorded = load_references(references)
    problems = []

    def entry(full, do_hash=True):
        rel = rel_posix(full, root)
        item = {"path": rel, "present": False, "size": None, "lastWriteUtc": None, "sha256": None,
                "referenceStatus": "no-recorded-reference"}
        try:
            if not os.path.isfile(full):
                return item
            stat = os.stat(full)
            item.update(present=True, size=stat.st_size, lastWriteUtc=datetime.datetime.fromtimestamp(
                stat.st_mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            if do_hash:
                item["sha256"] = sha256_file(full)
                known = recorded.get(rel.lower())
                if known:
                    item["referenceStatus"] = "matches-recorded" if known == item["sha256"] else "differs-from-recorded"
        except OSError as error:
            problems.append({"path": rel, "message": str(error)})
        return item

    def aggregate(entries):
        lines = sorted(e["path"] + ":" + e["sha256"] for e in entries if e["sha256"])
        return sha256_bytes("\n".join(lines).encode("utf-8")) if lines else None

    exe_path = next((ci_path(root, n) for n in EXE_NAMES if ci_path(root, n).is_file()), ci_path(root, EXE_NAMES[0]))
    exe = entry(exe_path)
    executable = {"file": exe, "pe": None}
    if not exe["present"]:
        problems.append({"path": exe["path"], "message": "no game executable found; is this an installation folder?"})
    if exe["present"]:
        try:
            executable["pe"] = read_pe(exe_path)
        except OSError as error:
            problems.append({"path": exe["path"], "message": str(error)})

    groups = []
    for group_id, pattern, parts, suffix, recursive in GROUPS:
        directory = ci_path(root, *parts)
        do_hash = hash_archives if group_id == "archives" else True
        found = []
        if directory.is_dir():
            walker = os.walk(directory) if recursive else [(str(directory), [], os.listdir(directory))]
            for base, _dirs, names in walker:
                for name in names:
                    full = os.path.join(base, name)
                    if os.path.isfile(full) and name.lower().endswith(suffix):
                        found.append(entry(full, do_hash))
        found.sort(key=lambda e: e["path"])
        matching = sum(e["referenceStatus"] == "matches-recorded" for e in found)
        differing = sum(e["referenceStatus"] == "differs-from-recorded" for e in found)
        group = {"id": group_id, "pattern": pattern, "count": len(found), "hashed": do_hash,
                 "matchesRecorded": matching, "differsFromRecorded": differing,
                 "noRecordedReference": len(found) - matching - differing,
                 "aggregateSha256": aggregate(found) if do_hash else None}
        if not aggregate_only:
            group["files"] = found
        groups.append(group)

    named = [entry(ci_path(root, "data", "script", n)) for n in ("main.scm", "script.img")]
    return {
        "schemaVersion": 1,
        "kind": "GTA San Andreas installation metadata for research provenance",
        "generatedUtc": utc_now(),
        "tool": {"name": "export_manifest.py", "version": TOOL_VERSION, "python": platform.python_version(),
                 "hashArchives": bool(hash_archives), "aggregateOnly": bool(aggregate_only)},
        "notes": [
            "Metadata only: no game files, binaries, scripts or assets are copied.",
            "matches-recorded means equal to a hash supplied with --reference; it does not prove a pristine original.",
            "Executable facts are for comparison; use identify_build.py and state the version confidence.",
            "Aggregate hash = SHA-256 of sorted 'installation-relative-path:sha256' lines joined with LF, UTF-8.",
            "The version resource is not read; a missing or present resource proves nothing about the build.",
        ],
        "complete": not problems,
        "installation": {"label": label, "executable": executable},
        "namedScriptFiles": named,
        "groups": groups,
        "referenceEntries": len(recorded),
        "problems": problems,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-dir", required=True)
    parser.add_argument("--output", required=True, help="JSON file outside the installation")
    parser.add_argument("--reference", action="append", default=[], help="JSON with earlier path/sha256 records")
    parser.add_argument("--label", help="your own name for this installation (never inferred from the folder)")
    parser.add_argument("--hash-archives", action="store_true", help="also hash models/*.img (slow)")
    parser.add_argument("--aggregate-only", action="store_true", help="omit per-file lists")
    args = parser.parse_args()
    manifest = build_manifest(args.game_dir, args.reference, args.hash_archives, args.aggregate_only, args.label)
    out = write_json(args.output, manifest)
    exe = manifest["installation"]["executable"]["file"]
    print("manifest: executable %s, %d groups, %d problems, complete=%s -> %s" % (
        "present" if exe["present"] else "missing", len(manifest["groups"]), len(manifest["problems"]),
        str(manifest["complete"]).lower(), out))
    return 0 if manifest["complete"] else 1


if __name__ == "__main__":
    run(main)

#!/usr/bin/env python3
"""Export ENEX (entrance/exit) or GRGE (garage) records from the text IPL files of an installation.

Read-only; emits facts with source file, line and SHA-256. Coverage is deliberately stated: binary IPLs and
IPLs streamed from archives are NOT scanned, so an absent record is not proof that it does not exist.
ENEX rows are raw portal volumes, not safe standing positions. A GRGE type is the file value; scripts can
change a garage at runtime, so a type name does not establish behavior.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep the installed skill folder unchanged

import argparse
import math
import os

from _common import (DevkitError, TOOL_VERSION, ci_path, game_root, rel_posix, run, sha256_bytes, utc_now,
                     write_json)


def _int_or_raw(text):
    try:
        return int(text)
    except ValueError:
        return text


def _numbers(parts):
    values = [float(p) for p in parts]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("non-finite number")
    return values


def parse_enex(parts):
    if len(parts) < 18:
        raise ValueError("expected at least 18 fields, found %d" % len(parts))
    n = _numbers(parts[:13])
    return {"name": parts[13].strip('"'), "entry": n[0:3], "entryAngle": n[3], "volume": n[4:7],
            "destination": n[7:10], "destinationAngle": n[10], "areaCode": int(n[11]), "flags": int(n[12]),
            "sky": _int_or_raw(parts[14]), "i2": _int_or_raw(parts[15]), "timeOn": _int_or_raw(parts[16]),
            "timeOff": _int_or_raw(parts[17])}


def parse_grge(parts):
    if len(parts) != 11:
        raise ValueError("expected 11 fields, found %d" % len(parts))
    n = _numbers(parts[:8])
    return {"name": parts[10].strip('"'), "base": n[0:3], "front": n[3:5], "opposite": n[5:8],
            "flags": int(parts[8]), "type": int(parts[9])}


SECTIONS = {
    "enex": (parse_enex, [
        "Raw portal volumes from the file, not validated standing or spawn positions.",
        "Names link portal pairs; areaCode is the interior number, not an exterior region.",
        "Field names follow community IPL documentation (X1 Y1 Z1 ROT W1 W2 C8 X2 Y2 Z2 Rot2 Int Flag Name Sky I2 TimeOn TimeOff); their meaning is documented, not verified here."]),
    "grge": (parse_grge, [
        "Raw records; not every garage that exists or functions in the game is guaranteed to be listed.",
        "Field names follow the gta-reversed garage loader; meaning is source-derived, not verified here.",
        "type is the file value; a script may change a garage at runtime."]),
}


def export_records(game_dir, section: str) -> dict:
    if section not in SECTIONS:
        raise DevkitError("unknown section: " + section)
    parser, notes = SECTIONS[section]
    root = game_root(game_dir)
    maps = ci_path(root, "data", "maps")
    if not maps.is_dir():
        raise DevkitError("missing data/maps under %s" % root)
    files = []
    for base, _dirs, names in os.walk(maps):
        files += [os.path.join(base, n) for n in names if n.lower().endswith(".ipl")]
    files.sort(key=lambda f: rel_posix(f, root))

    records, sources, problems, text_count, binary_count = [], [], [], 0, 0
    for full in files:
        rel = rel_posix(full, root)
        try:
            with open(full, "rb") as handle:
                data = handle.read()
        except OSError as error:
            problems.append({"path": rel, "line": None, "message": str(error)})
            continue
        if data[:4] == b"bnry":
            binary_count += 1
            continue
        text_count += 1
        inside, found, unterminated = False, [], False
        for number, raw in enumerate(data.decode("latin-1").splitlines(), start=1):
            line = raw.strip()
            lowered = line.lower()
            if lowered == section:
                inside = True
                continue
            if inside and lowered.startswith("end"):
                inside = False
                continue
            if not inside or not line or line.startswith("#"):
                continue
            try:
                record = parser([p.strip() for p in line.split(",")])
            except (ValueError, OverflowError) as error:
                problems.append({"path": rel, "line": number, "message": "invalid %s row: %s" % (section.upper(), error)})
                continue
            found.append({"source": rel, "line": number, **record})
        if inside:
            unterminated = True
            problems.append({"path": rel, "line": None, "message": "section '%s' has no end marker" % section})
        if found or unterminated:
            sources.append({"path": rel, "sha256": sha256_bytes(data)})
            records += found

    return {
        "schemaVersion": 1,
        "kind": "GTA San Andreas %s records from text IPL files" % section.upper(),
        "generatedUtc": utc_now(),
        "tool": {"name": "export_ipl_records.py", "version": TOOL_VERSION},
        "section": section,
        "notes": notes + ["No binaries, models, textures, scripts or complete IPL files are copied."],
        "coverage": {"textIplScanned": text_count, "binaryIplSkipped": binary_count,
                     "archiveStreamedIplScanned": False,
                     "statement": "Partial by design: only text IPLs under data/maps were read."},
        "complete": not problems,
        "problems": problems,
        "sources": sources,
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-dir", required=True)
    parser.add_argument("--section", required=True, choices=sorted(SECTIONS))
    parser.add_argument("--output", required=True, help="JSON file outside the installation")
    args = parser.parse_args()
    document = export_records(args.game_dir, args.section)
    out = write_json(args.output, document)
    print("%s: %d records from %d sources (%d text, %d binary skipped), %d problems, complete=%s -> %s" % (
        args.section, len(document["records"]), len(document["sources"]), document["coverage"]["textIplScanned"],
        document["coverage"]["binaryIplSkipped"], len(document["problems"]), str(document["complete"]).lower(), out))
    return 0 if document["complete"] else 1


if __name__ == "__main__":
    run(main)

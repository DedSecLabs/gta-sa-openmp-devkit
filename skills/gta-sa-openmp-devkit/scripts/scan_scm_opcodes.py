#!/usr/bin/env python3
"""Report where an SCM opcode appears in PRIVATE COPIES of main.scm and script.img.

This is a byte-pattern scan, not a disassembly: an opcode word followed by a plausible argument type is
reported with a best-effort decode of up to three literal arguments. Instruction boundaries are NOT verified,
so a hit can be a false positive and a miss is never proof of absence (arguments held in variables, arrays or
other encodings are invisible to it). Use it to cross-check a decompile, not to replace one.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep the installed skill folder unchanged

import argparse
import math
import struct

from _common import (DevkitError, TOOL_VERSION, absolute, find_install_root, parse_hex, run, sha256_bytes,
                     utc_now, write_json)

PLAUSIBLE = {0, 1, 2, 3, 4, 5, 6, 9}


def _private_copy(path, what):
    full = absolute(path)
    if not full.is_file():
        raise DevkitError("%s not found: %s" % (what, full))
    if find_install_root(full) is not None:
        raise DevkitError("%s must be a private copy outside the game installation" % what)
    return full


def decode_args(data: bytes, start: int):
    out, p, limit = [], start, len(data)
    for _ in range(3):
        if p >= limit:
            break
        kind = data[p]
        p += 1
        sizes = {1: ("int32", "<i", 4), 2: ("globalVar", "<H", 2), 3: ("localVar", "<H", 2),
                 4: ("int8", "<b", 1), 5: ("int16", "<h", 2), 6: ("float", "<f", 4)}
        if kind in sizes:
            name, fmt, size = sizes[kind]
            if p + size > limit:
                break
            value = struct.unpack_from(fmt, data, p)[0]
            if isinstance(value, float) and not math.isfinite(value):
                value = repr(value)
            out.append({"type": name, "value": value})
            p += size
        elif kind == 9:
            if p + 8 > limit:
                break
            out.append({"type": "string8", "value": data[p:p + 8].split(b"\0")[0].decode("latin-1")})
            p += 8
        elif kind == 0:
            break
        else:
            out.append({"type": "unknown0x%02X" % kind, "value": None})
            break
    return out


def scan(data: bytes, label: str, opcodes, known, max_hits: int, excerpt: int):
    hits, summary = [], []
    for op in opcodes:
        lo, hi = op & 0xFF, (op >> 8) & 0x7F
        positions = set()
        for pattern in (bytes([lo, hi]), bytes([lo, hi | 0x80])):
            at = data.find(pattern)
            while at != -1:
                positions.add(at)
                at = data.find(pattern, at + 1)
        total, skipped = 0, 0
        for i in sorted(positions):
            if i > len(data) - 4:
                continue
            if data[i + 2] not in PLAUSIBLE:
                skipped += 1
                continue
            decoded = decode_args(data, i + 2)
            strings = [a["value"].lower() for a in decoded if a["type"] == "string8"]
            match = any(s in known for s in strings) if known else None
            if known and not match:
                skipped += 1
                continue
            total += 1
            if total > max_hits:
                continue
            hits.append({"source": label, "offset": "0x%X" % i, "opcode": "%04X" % op,
                         "notFlag": bool(data[i + 1] & 0x80), "args": decoded, "knownStringMatch": match,
                         "excerptHex": data[i:i + excerpt + 2].hex(" ")})
        summary.append({"source": label, "opcode": "%04X" % op, "reported": min(total, max_hits),
                        "totalMatching": total, "truncated": total > max_hits,
                        "rejectedByTypeOrFilter": skipped})
    return hits, summary


def read_img_entries(img: bytes):
    """Yield (name, bytes) for a VER2 archive; returns entries and a list of problems."""
    problems, entries = [], []
    if len(img) < 8 or img[:4] != b"VER2":
        raise DevkitError("script.img is not a VER2 archive")
    count = struct.unpack_from("<i", img, 4)[0]
    if count < 0 or 8 + 32 * count > len(img):
        raise DevkitError("script.img directory is malformed (entry count %d does not fit the file)" % count)
    for e in range(count):
        at = 8 + 32 * e
        offset = struct.unpack_from("<I", img, at)[0] * 2048
        sectors = struct.unpack_from("<H", img, at + 4)[0] or struct.unpack_from("<H", img, at + 6)[0]
        name = img[at + 8:at + 32].split(b"\0")[0].decode("latin-1")
        length = sectors * 2048
        if offset >= len(img):
            problems.append({"entry": name, "message": "offset lies outside the archive; entry skipped"})
            continue
        if offset + length > len(img):
            problems.append({"entry": name, "message": "entry is cut short by the end of the archive"})
            length = len(img) - offset
        entries.append((name, img[offset:offset + length]))
    return entries, problems


def build_facts(scm_path, opcodes, img_path=None, known_strings=(), max_hits=500, excerpt=24) -> dict:
    if not opcodes:
        raise DevkitError("give at least one --opcode")
    ops = []
    for text in opcodes:
        value = parse_hex(text)
        if not 0 <= value <= 0x7FFF:
            raise DevkitError("opcode out of range: %s" % text)
        ops.append(value)
    known = {s.lower() for s in known_strings}
    scm_full = _private_copy(scm_path, "main.scm")
    data = scm_full.read_bytes()
    inputs = [{"name": "main.scm", "size": len(data), "sha256": sha256_bytes(data)}]
    hits, summary = scan(data, "main.scm", ops, known, max_hits, excerpt)
    problems, entry_count = [], 0
    if img_path:
        img = _private_copy(img_path, "script.img").read_bytes()
        inputs.append({"name": "script.img", "size": len(img), "sha256": sha256_bytes(img)})
        entries, problems = read_img_entries(img)
        entry_count = len(entries)
        for name, chunk in entries:
            more_hits, more_summary = scan(chunk, "script.img:" + name, ops, known, max_hits, excerpt)
            hits += more_hits
            summary += [row for row in more_summary if row["totalMatching"] or row["rejectedByTypeOrFilter"]]
    truncated = any(row["truncated"] for row in summary)
    return {
        "schemaVersion": 1,
        "kind": "SCM opcode occurrence facts (byte-pattern scan, not a disassembly)",
        "generatedUtc": utc_now(),
        "tool": {"name": "scan_scm_opcodes.py", "version": TOOL_VERSION},
        "notes": [
            "Offsets are file offsets (main.scm) or entry-relative offsets (script.img entries).",
            "Instruction boundaries are not verified; confirm each hit against a decompile before relying on it.",
            "Only literal arguments are decoded. Zero hits is not proof that a command is unused.",
            "excerptHex is a short raw window; no bulk script content is written.",
        ],
        "complete": not problems and not truncated,
        "coverage": {"mainScm": True, "scriptImg": bool(img_path),
                     "statement": "'complete' means the inputs given were scanned without truncation or damage. "
                                  + ("Both script files were scanned." if img_path else
                                     "script.img was NOT scanned, so external scripts are not covered.")},
        "inputs": inputs,
        "opcodes": ["%04X" % o for o in ops],
        "knownStringCount": len(known),
        "imgEntries": entry_count,
        "problems": problems,
        "summary": summary,
        "hits": hits,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scm", required=True, help="private copy of main.scm")
    parser.add_argument("--img", help="private copy of script.img (optional)")
    parser.add_argument("--opcode", action="append", default=[], help="hexadecimal opcode, e.g. 00A5 (repeatable)")
    parser.add_argument("--known-string", action="append", default=[], help="keep only hits with this string8 argument")
    parser.add_argument("--max-hits", type=int, default=500)
    parser.add_argument("--excerpt-bytes", type=int, default=24)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.max_hits < 1 or not 0 <= args.excerpt_bytes <= 64:
        raise DevkitError("--max-hits must be positive and --excerpt-bytes between 0 and 64")
    facts = build_facts(args.scm, args.opcode, args.img, args.known_string, args.max_hits, args.excerpt_bytes)
    out = write_json(args.output, facts)
    print("scm opcode facts: %d hits, %d inputs, %d script.img entries, complete=%s -> %s" % (
        len(facts["hits"]), len(facts["inputs"]), facts["imgEntries"], str(facts["complete"]).lower(), out))
    return 0 if facts["complete"] else 1


if __name__ == "__main__":
    run(main)

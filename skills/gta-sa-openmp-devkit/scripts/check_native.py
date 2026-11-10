#!/usr/bin/env python3
"""Check that a Pawn function, callback or #define is declared in the include files you actually build with.

Usage: check_native.py NAME [NAME ...] --include-dir DIR [--include-dir DIR ...]

Include directories default to target.includeDirs in gta-sa-openmp-devkit.json. Comments are ignored. Each match
says whether it is available under preprocessing:

  unconditional  outside any #if block
  conditional    depends on a condition this tool cannot evaluate (listed in 'conditions'): inside such an
                 #if, in a later branch of one, or after an #endinput that such a condition may have reached
  disabled       inside '#if 0', a branch that cannot be taken, or after an unconditional '#endinput'

This is not a preprocessor: only literal conditions are decided and uncertainty is never dropped.
Include guards remain conditional too: the scanner does not know the caller's defines or include order.

A name is 'declared' only when at least one match is unconditional. A 'conditional' result means you must
read the listed conditions against the project's defines. "not-found" means no supported declaration matched
in the folders searched; plugin natives live in their own includes. Enum members, const variables and
multiline declarations are not detected. A textual declaration does not prove runtime availability.

Exit code 0 = every name declared; 1 = at least one name is conditional, disabled or not found.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep the installed skill folder unchanged

import argparse
import json
import os
import re

from _common import DevkitError, load_profile, run

EXTENSIONS = (".inc", ".pwn", ".p", ".pawn")
DIRECTIVE = re.compile(r"^\s*#\s*(if|elseif|else|endif|endinput)\b(.*)$")
FALSE, TRUE = {"0", "false", "(0)"}, {"1", "true", "(1)"}


def strip_comments(line: str, in_block: bool):
    """Remove // and /* */ comments from one line, honouring string literals. Returns (code, in_block)."""
    out, i, quote = [], 0, None
    while i < len(line):
        if in_block:
            end = line.find("*/", i)
            if end < 0:
                return "".join(out), True
            i, in_block = end + 2, False
            out.append(" ")
            continue
        char = line[i]
        if quote:
            out.append(char)
            if char == "\\" and i + 1 < len(line):
                out.append(line[i + 1])
                i += 1
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            out.append(char)
        elif line.startswith("//", i):
            break
        elif line.startswith("/*", i):
            in_block = True
            i += 1
        else:
            out.append(char)
        i += 1
    return "".join(out), in_block


def _literal(condition: str) -> str:
    text = condition.strip().lower()
    return "off" if text in FALSE else "on" if text in TRUE else "unknown"


def scan_file(path, patterns):
    """Yield (name, line number, declaration, availability, conditions) for one file.

    Deliberately not a preprocessor. Only literal 0/1 conditions are decided; everything else is 'unknown',
    and uncertainty is never dropped: a branch after an unknown branch is itself unknown, and an #endinput
    inside an unknown branch leaves the rest of the file conditional. A later #define cannot undo the
    possibility that the file already ended, including for an apparent include guard.
    """
    stack, in_block = [], False   # frames: {"state", "condition", "taken", "maybe"}
    ended = None                  # None, "certain", or the condition that may have ended the file
    with open(path, "r", encoding="latin-1") as handle:
        for number, raw in enumerate(handle, start=1):
            code, in_block = strip_comments(raw.rstrip("\r\n"), in_block)
            if not code.strip():
                continue
            states = [frame["state"] for frame in stack]
            if ended == "certain" or "off" in states:
                availability = "disabled"
            elif "unknown" in states or ended:
                availability = "conditional"
            else:
                availability = "unconditional"
            directive = DIRECTIVE.match(code)
            if directive:
                word, rest = directive.group(1), directive.group(2).strip()
                if word == "if":
                    state = _literal(rest)
                    stack.append({"state": state, "condition": rest, "taken": state == "on",
                                  "maybe": state == "unknown"})
                elif word == "elseif" and stack:
                    frame = stack[-1]
                    literal = _literal(rest)
                    previous = frame["condition"]
                    if frame["taken"] or literal == "off":
                        frame["state"] = "off"
                    elif literal == "on" and not frame["maybe"]:
                        frame.update(state="on", taken=True)
                    else:  # unknown itself, or true only if an earlier unknown branch was false
                        frame.update(state="unknown", maybe=True)
                    frame["condition"] = "%s, after: %s" % (rest, previous)
                    # A true fallback exhausts this chain even if earlier branches were unknown.
                    if literal == "on":
                        frame["taken"] = True
                elif word == "else" and stack:
                    frame = stack[-1]
                    if frame["taken"]:
                        frame["state"] = "off"
                    elif frame["maybe"]:
                        frame.update(state="unknown", condition="else of: " + frame["condition"])
                    else:
                        frame.update(state="on", taken=True)
                elif word == "endif" and stack:
                    stack.pop()
                elif word == "endinput":
                    if "off" in states or ended == "certain":
                        pass                      # unreachable
                    elif "unknown" not in states:
                        ended = "certain"         # reached whenever the file got this far
                    elif ended is None:
                        ended = "after possible #endinput under: " + " && ".join(
                            f["condition"] for f in stack if f["state"] == "unknown")
                continue
            for name, pattern in patterns.items():
                if name in code and pattern.match(code):
                    conditions = [f["condition"] for f in stack if f["state"] != "on"]
                    if ended:
                        conditions.append("after #endinput" if ended == "certain" else ended)
                    yield name, number, code.strip()[:240], availability, conditions


def find_declarations(names, include_dirs) -> dict:
    directories = [os.path.abspath(d) for d in include_dirs]
    missing = [d for d in directories if not os.path.isdir(d)]
    if missing:
        raise DevkitError("include directory not found: " + ", ".join(missing))
    if not directories:
        raise DevkitError("no include directories given (use --include-dir or target.includeDirs in the profile)")
    patterns = {}
    for name in names:
        if not re.match(r"^[A-Za-z_@][A-Za-z0-9_@]*$", name):
            raise DevkitError("not a Pawn identifier: %r" % name)
        escaped = re.escape(name)
        patterns[name] = re.compile(
            r"^\s*(?:(?:native|forward|stock|public|static\s+stock)\s+(?:[A-Za-z_@][\w@]*:\s*)?%s\s*\("
            r"|#\s*define\s+%s\b)" % (escaped, escaped))
    results = {name: [] for name in names}
    scanned = 0
    for directory in directories:
        for base, _dirs, files in os.walk(directory):
            for file_name in sorted(files):
                if not file_name.lower().endswith(EXTENSIONS):
                    continue
                scanned += 1
                full = os.path.join(base, file_name)
                try:
                    for name, number, declaration, availability, conditions in scan_file(full, patterns):
                        results[name].append({"file": full, "line": number, "declaration": declaration,
                                              "availability": availability, "conditions": conditions})
                except OSError:
                    continue
    report = []
    for name, found in results.items():
        kinds = {item["availability"] for item in found}
        status = ("declared" if "unconditional" in kinds else "conditional" if "conditional" in kinds else
                  "disabled" if "disabled" in kinds else "not-found")
        report.append({"name": name, "status": status, "declared": status == "declared",
                       "textualMatches": len(found), "declarations": found})
    return {
        "includeDirs": directories,
        "filesScanned": scanned,
        "names": report,
        "note": "declared = a textual declaration with no unresolved condition in this file. This does not "
                "prove that the project includes the file or that the runtime provides the symbol. "
                "conditional = inspect the listed conditions, including include guards, against the actual "
                "build. not-found = no supported declaration was matched; never invent a replacement native.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="+")
    parser.add_argument("--include-dir", action="append", default=[])
    args = parser.parse_args()
    include_dirs = args.include_dir
    if not include_dirs:
        profile_path, profile = load_profile()
        configured = (profile.get("target") or {}).get("includeDirs") or []
        base = os.path.dirname(str(profile_path)) if profile_path else "."
        include_dirs = [d if os.path.isabs(d) else os.path.join(base, d) for d in configured]
    report = find_declarations(args.names, include_dirs)
    print(json.dumps(report, indent=1))
    return 0 if all(item["declared"] for item in report["names"]) else 1


if __name__ == "__main__":
    run(main)

#!/usr/bin/env python3
"""Check finding records: every claim names its build, layer, evidence class and a source that can carry it.

Usage: validate_findings.py FILE_OR_DIR [...] [--verify-files ROOT]

The rules are those in references/evidence.md (for example, an "exe-byte" claim needs an executable source
and the executable's hash). With
--verify-files, file sources are re-hashed under ROOT so findings whose source changed are reported as stale
instead of being silently reused, and sources that cannot be found count as unverified, not as passed.
Exit code 0 = records valid and any requested verification complete; 1 = structural errors;
3 = records valid but verification found stale or missing sources.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep the installed skill folder unchanged

import argparse
import json
import re
from pathlib import Path

from _common import DevkitError, ci_path, is_sha256, read_json, run, sha256_file

LAYERS = {"scm", "engine", "data", "runtime"}
CLASSES = {"original-observed", "exe-byte", "source-derived", "documented", "inferred"}
CONFIDENCE = {"confirmed", "corroborated", "documented-only"}
SOURCE_FIELDS = {
    "file": ("path", "sha256"),
    "repository": ("url", "commit", "path"),
    "executable": ("sha256", "addressKind", "address"),
    "probe": ("date", "observer", "description"),
    "documentation": ("title", "retrieved"),
}
NEEDS = {  # evidence class -> source types of which at least one must be present
    "original-observed": {"file", "probe"},
    "exe-byte": {"executable"},
    "source-derived": {"repository"},
    "documented": {"documentation"},
}
ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HEX = re.compile(r"^0x[0-9A-Fa-f]+$")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def one_of(value, options) -> bool:
    """Membership that tolerates any JSON type (lists and objects are not hashable)."""
    return isinstance(value, str) and value in options


def check_finding(finding, where, errors):
    def bad(message):
        errors.append("%s: %s" % (where, message))

    if not isinstance(finding, dict):
        return bad("finding must be an object")
    if not (text(finding.get("id")) and ID.match(finding["id"])):
        bad("id must be lowercase words joined by hyphens")
    if not text(finding.get("claim")):
        bad("claim is required")
    if not one_of(finding.get("layer"), LAYERS):
        bad("layer must be one of " + ", ".join(sorted(LAYERS)))
    evidence = finding.get("evidenceClass")
    if not one_of(evidence, CLASSES):
        evidence = None
        bad("evidenceClass must be one of " + ", ".join(sorted(CLASSES)))
    build = finding.get("build")
    if not isinstance(build, dict) or not text(build.get("label")) or not one_of(build.get("confidence"), CONFIDENCE):
        bad("build needs a label and a confidence (confirmed, corroborated or documented-only)")
        build = {}
    if build.get("exeSha256") is not None and not is_sha256(build.get("exeSha256")):
        bad("build.exeSha256 must be a SHA-256")
        build = dict(build, exeSha256=None)

    sources = finding.get("sources")
    if not isinstance(sources, list):
        bad("sources must be a list")
        sources = []
    kinds = set()
    for index, source in enumerate(sources):
        label = "sources[%d]" % index
        if not isinstance(source, dict) or not one_of(source.get("type"), SOURCE_FIELDS):
            bad(label + ": type must be one of " + ", ".join(sorted(SOURCE_FIELDS)))
            continue
        kind = source["type"]
        kinds.add(kind)
        for field in SOURCE_FIELDS[kind]:
            if not text(source.get(field)):
                bad("%s (%s): %s is required (text)" % (label, kind, field))
                source = dict(source, **{field: None})
        if kind == "file" and text(source.get("sha256")) and not is_sha256(source["sha256"]):
            bad(label + ": sha256 is not a SHA-256")
        if kind == "repository" and text(source.get("commit")) and not COMMIT.match(source["commit"]):
            bad(label + ": commit must be a pinned commit hash, not a branch or tag")
        if kind == "executable":
            if text(source.get("sha256")) and not is_sha256(source["sha256"]):
                bad(label + ": sha256 is not a SHA-256")
            if not one_of(source.get("addressKind"), ("va", "rva", "fileOffset")):
                bad(label + ": addressKind must be va, rva or fileOffset; never leave the kind implicit")
            if text(source.get("address")) and not HEX.match(source["address"]):
                bad(label + ": address must be hexadecimal with a 0x prefix")
            if build.get("exeSha256") and is_sha256(source.get("sha256")) and \
                    source["sha256"].lower() != build["exeSha256"].lower():
                bad(label + ": executable hash differs from build.exeSha256; addresses are build-specific")
        if kind in ("probe", "documentation"):
            field = "date" if kind == "probe" else "retrieved"
            if text(source.get(field)) and not DATE.match(source[field]):
                bad("%s: %s must start with YYYY-MM-DD" % (label, field))

    if evidence in NEEDS and not (kinds & NEEDS[evidence]):
        bad("evidenceClass '%s' needs a source of type %s" % (evidence, " or ".join(sorted(NEEDS[evidence]))))
    if evidence == "exe-byte" and not is_sha256(build.get("exeSha256")):
        bad("an exe-byte claim needs build.exeSha256, because addresses apply to one executable only")
    implementation = finding.get("implementation")
    if implementation is not None and (not isinstance(implementation, dict) or
                                       not one_of(implementation.get("status"), ("none", "planned", "implemented"))):
        bad("implementation must be an object whose status is none, planned or implemented")
        implementation = None
    if evidence == "inferred":
        if not text(finding.get("notExamined")):
            bad("an inferred claim must say what was not examined (notExamined)")
        if implementation and implementation["status"] == "implemented":
            bad("an inferred claim cannot be marked implemented; verify it or record the implementation as an authored choice")
    if "conflictsWith" in finding and not (isinstance(finding["conflictsWith"], list) and
                                            all(text(x) for x in finding["conflictsWith"])):
        bad("conflictsWith must be a list of finding ids")


def collect(paths):
    files = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files += sorted(p for p in path.rglob("*.json"))
        elif path.is_file():
            files.append(path)
        else:
            raise DevkitError("not found: %s" % path)
    if not files:
        raise DevkitError("no finding files to check")
    return files


def validate(paths, verify_root=None) -> dict:
    """Structural validity and source verification are reported separately.

    'structureValid' is about the records. 'verification' is about the world: it is complete only when every
    file source was found under the root and still matches its hash.
    """
    errors, stale, missing, seen, pending_conflicts, count, verified = [], [], [], {}, [], 0, 0
    if verify_root is not None and not Path(verify_root).is_dir():
        raise DevkitError("verification root is not a folder: %s" % verify_root)
    for path in collect(paths):
        document = read_json(path)
        findings = document.get("findings") if isinstance(document, dict) else None
        if not isinstance(findings, list):
            errors.append("%s: expected an object with a 'findings' list" % path)
            continue
        if document.get("schemaVersion") != 1:
            errors.append("%s: schemaVersion must be 1" % path)
        for index, finding in enumerate(findings):
            count += 1
            identifier = finding.get("id") if isinstance(finding, dict) else None
            where = "%s#%s" % (path, identifier or index)
            check_finding(finding, where, errors)
            if not isinstance(finding, dict):
                continue
            if text(identifier):
                if identifier in seen:
                    errors.append("%s: duplicate id (first used in %s)" % (where, seen[identifier]))
                seen.setdefault(identifier, str(path))
            conflicts = finding.get("conflictsWith")
            for other in conflicts if isinstance(conflicts, list) else []:
                if text(other):
                    pending_conflicts.append((where, other))
            sources = finding.get("sources")
            if verify_root is not None:
                for source in sources if isinstance(sources, list) else []:
                    if isinstance(source, dict) and source.get("type") == "file" and text(source.get("path")) \
                            and is_sha256(source.get("sha256")):
                        parts = [p for p in source["path"].replace("\\", "/").split("/") if p not in ("", ".")]
                        if ".." in parts or ":" in source["path"] or source["path"].startswith(("/", "\\")):
                            errors.append("%s: file source path must be installation-relative: %s" % (where, source["path"]))
                            continue
                        target = ci_path(verify_root, *parts)
                        if not target.is_file():
                            missing.append("%s: %s is not present under the given root" % (where, source["path"]))
                        elif sha256_file(target) != source["sha256"].lower():
                            stale.append("%s: %s no longer matches its recorded hash" % (where, source["path"]))
                        else:
                            verified += 1
    for where, other in pending_conflicts:
        if other not in seen:
            errors.append("%s: conflictsWith refers to unknown id '%s'" % (where, other))
    requested = verify_root is not None
    verification = {"requested": requested, "verified": verified, "stale": stale, "missing": missing,
                    "complete": requested and not stale and not missing}
    structure_valid = not errors
    return {"findings": count, "structureValid": structure_valid, "errors": errors, "verification": verification,
            "ok": structure_valid and (not requested or verification["complete"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--verify-files", metavar="ROOT", help="re-hash file sources relative to this folder")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate(args.paths, args.verify_files)
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        check = result["verification"]
        for line in result["errors"]:
            print("error: " + line)
        for line in check["stale"]:
            print("stale: " + line)
        for line in check["missing"]:
            print("missing: " + line)
        print("structure: %d findings, %d errors" % (result["findings"], len(result["errors"])))
        if check["requested"]:
            print("verification: %d sources verified, %d stale, %d missing -> %s" % (
                check["verified"], len(check["stale"]), len(check["missing"]),
                "complete" if check["complete"] else "INCOMPLETE"))
        else:
            print("verification: not requested (use --verify-files ROOT)")
    if not result["structureValid"]:
        return 1
    return 0 if result["ok"] else 3


if __name__ == "__main__":
    run(main)

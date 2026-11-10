#!/usr/bin/env python3
"""Report which DevKit workflows are possible on this machine, before any research starts.

Nothing is installed, downloaded or started. For each workflow the report says whether it is available and,
when it is not, the narrower path that still is. A missing tool narrows the research; it never justifies a
guessed finding.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep the installed skill folder unchanged

import argparse
import json
import os
import platform
import shutil

from _common import EXE_NAMES, TOOL_VERSION, ci_path, load_profile, run


def _dir(profile_dir, value):
    if not value:
        return None
    return value if os.path.isabs(value) else os.path.join(profile_dir, value)


def report(start=None) -> dict:
    profile_path, profile = load_profile(start)
    base = os.path.dirname(str(profile_path)) if profile_path else os.getcwd()
    game = profile.get("game") or {}
    tools = profile.get("tools") or {}
    refs = profile.get("references") or {}
    target = profile.get("target") or {}
    policies = profile.get("policies") or {}

    game_dir = _dir(base, game.get("installDir"))
    has_game = bool(game_dir and os.path.isdir(game_dir) and any(ci_path(game_dir, n).is_file() for n in EXE_NAMES))
    sanny_dir = _dir(base, tools.get("sannyDir"))
    has_sanny = bool(sanny_dir and ci_path(sanny_dir, "sanny.exe").is_file())
    workspace = _dir(base, tools.get("privateWorkspace"))
    has_workspace = bool(workspace and os.path.isdir(workspace))
    include_dirs = [_dir(base, d) for d in target.get("includeDirs") or []]
    has_includes = bool(include_dirs) and all(os.path.isdir(d) for d in include_dirs)

    def checkout(key):
        entry = refs.get(key) or {}
        path = _dir(base, entry.get("path"))
        return {"configured": bool(entry), "present": bool(path and os.path.isdir(path)),
                "commitPinned": bool(entry.get("commit"))}

    reversed_src, sdk = checkout("gtaReversed"), checkout("pluginSdk")

    def flow(name, available, needs, fallback):
        return {"workflow": name, "available": bool(available), "needs": needs,
                "fallback": None if available else fallback}

    workflows = [
        flow("identify-build", has_game, "game.installDir with the executable",
             "Ask for the executable's path, or treat the build as documented-only and say so."),
        flow("installation-manifest", has_game, "game.installDir",
             "Work from hashes the project already recorded; do not assume the files match."),
        flow("data-layer-export", has_game, "game.installDir with data/maps",
             "Cite previously recorded exports with their hashes; otherwise the claim stays documented or inferred."),
        flow("scm-opcode-scan", has_workspace, "tools.privateWorkspace holding private copies of main.scm/script.img",
             "Ask the owner to copy the scripts to a private folder; never read them in place."),
        flow("scm-decompile", has_sanny and has_game and has_workspace and os.name == "nt",
             "Windows, tools.sannyDir, game.installDir and tools.privateWorkspace",
             "Use an already-authorized Windows connection or a user-run Windows handoff (references/scm.md). "
             "Otherwise reuse applicable provenance-checked findings; an opcode scan alone cannot prove script behavior."),
        flow("engine-source-reading", reversed_src["present"] or sdk["present"],
             "a pinned gta-reversed or Plugin-SDK checkout in references",
             "Cite the public repository at an exact commit; results are source-derived at best."),
        flow("executable-byte-check", has_game and bool(shutil.which("objdump")),
             "game.installDir and a disassembler such as objdump",
             "identify_build.py --probe can still hash byte ranges; without a disassembler make no claim about code."),
        flow("pawn-declaration-check", has_includes, "target.includeDirs",
             "State that the API was not verified against the pinned includes."),
    ]
    return {
        "tool": "capabilities.py " + TOOL_VERSION,
        "python": platform.python_version(),
        "platform": sys.platform,
        "scope": "Local machine and accessible paths only; remote execution and permissions are not detected.",
        "profile": str(profile_path) if profile_path else None,
        "profileHint": None if profile_path else "No gta-sa-openmp-devkit.json found; copy the skill's assets/project-profile.template.json "
                                                 "to the project root as gta-sa-openmp-devkit.json and fill in what applies.",
        "policies": {"cachedEvidence": policies.get("cachedEvidence", "forbidden"),
                     "installTools": policies.get("installTools", "ask"),
                     "startGame": policies.get("startGame", "ask")},
        "references": {"gtaReversed": reversed_src, "pluginSdk": sdk},
        "pathTools": {name: bool(shutil.which(name)) for name in ("git", "objdump")},
        "workflows": workflows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", help="folder to start the profile search from (default: current folder)")
    args = parser.parse_args()
    print(json.dumps(report(args.project), indent=1))


if __name__ == "__main__":
    run(main)

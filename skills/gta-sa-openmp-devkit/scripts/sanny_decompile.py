#!/usr/bin/env python3
"""Bounded, non-interactive Sanny Builder decompile of a PRIVATE COPY of an SCM file (Windows).

Sanny Builder keeps the game directory per edit mode in data/settings.ini ([<mode id>] GamePath=...); without
it the command line waits for a dialog and never exits. This wrapper sets that key for the run and then puts
settings.ini back exactly as it was, verifies the input hash before and after, enforces a timeout, and
refuses inputs or outputs inside a game installation. The decompiled text is original-game content: keep it
private and out of version control.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep the installed skill folder unchanged

import argparse
import json
import os
import subprocess

from _common import (DevkitError, TOOL_VERSION, absolute, ci_path, find_install_root, game_root, is_within, run,
                     sha256_file, EXE_NAMES)


def patched_settings(original: bytes, mode_id: str, game_path: str) -> bytes:
    """Return settings.ini content with GamePath set in [mode_id], every other line preserved."""
    lines = original.decode("latin-1").splitlines()
    result, inside, seen, written = [], False, False, False
    setting = "GamePath=" + game_path
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if inside and not written:
                result.append(setting)
                written = True
            inside = stripped[1:-1].strip().lower() == mode_id.lower()
            seen = seen or inside
        elif inside and stripped.lower().replace(" ", "").startswith("gamepath="):
            if not written:
                result.append(setting)
                written = True
            continue
        result.append(line)
    if inside and not written:
        result.append(setting)
    if not seen:
        result += ["[" + mode_id + "]", setting]
    return ("\r\n".join(result) + "\r\n").encode("latin-1")


def decompile(sanny_dir, game_dir, scm, output, expected_sha256=None, game="sa", mode_id="sa_sbl",
              timeout=120.0, hex_offsets=True, launcher=()) -> dict:
    """launcher: command prefix used to start sanny.exe (the tests use the Python interpreter)."""
    sanny_root = absolute(sanny_dir)
    sanny = ci_path(sanny_root, "sanny.exe")
    if not sanny.is_file():
        raise DevkitError("sanny.exe not found in %s" % sanny_root)
    # The installation path lives in its own variable. An earlier wrapper reused the name of the --game
    # parameter for it (case-insensitive in PowerShell) and passed the directory as the game identifier.
    install_dir = game_root(game_dir)
    if not any(ci_path(install_dir, name).is_file() for name in EXE_NAMES):
        raise DevkitError("game directory does not contain a game executable: %s" % install_dir)
    if not game.replace("_", "").isalnum() or not mode_id.replace("_", "").isalnum():
        raise DevkitError("--game and --mode-id must be plain identifiers such as 'sa' and 'sa_sbl'")
    scm_path = absolute(scm)
    if not scm_path.is_file():
        raise DevkitError("input not found: %s" % scm_path)
    if find_install_root(scm_path) is not None:
        raise DevkitError("input must be a private copy outside the game installation")
    out_path = absolute(output)
    if find_install_root(out_path) is not None or is_within(out_path, install_dir):
        raise DevkitError("output path must be outside the game installation")
    if is_within(out_path, sanny_root):
        raise DevkitError("output path must be outside the Sanny Builder folder")
    if out_path.is_dir():
        raise DevkitError("output path is a directory")
    # The output is deleted before the run, so it must never be the input under any name (same path, different
    # case, a link, or a hard link to the same file).
    same_name = os.path.normcase(os.path.realpath(out_path)) == os.path.normcase(os.path.realpath(scm_path))
    if same_name or (out_path.exists() and os.path.samefile(out_path, scm_path)):
        raise DevkitError("output path is the input file; choose a different output")
    if timeout <= 0:
        raise DevkitError("timeout must be positive")

    before = sha256_file(scm_path)
    if expected_sha256 and before != expected_sha256.lower():
        raise DevkitError("input hash differs from the expected value: " + before)

    settings = ci_path(sanny_root, "data", "settings.ini")
    backup = settings.with_name(settings.name + ".devkit-backup")
    if backup.is_file():
        # A previous run was interrupted before it could restore the settings; do that first.
        settings.write_bytes(backup.read_bytes())
        backup.unlink()
    had_settings = settings.is_file()
    original = settings.read_bytes() if had_settings else b""
    if original[:2] in (b"\xff\xfe", b"\xfe\xff"):
        raise DevkitError("settings.ini is UTF-16; set GamePath for [%s] in Sanny Builder yourself and re-run" % mode_id)
    created_data_dir = not settings.parent.is_dir()
    arguments = [*launcher, str(sanny), "--decompile", str(scm_path), str(out_path), "--game", game, "--no-splash",
                 "-o", "Editor::ShowReport", "0", "-o", "Editor::ShowProgress", "0",
                 "-o", "Decompiler::OverwriteOutputFile", "1", "-o", "Decompiler::ManualIMGOpening", "0"]
    if hex_offsets:
        # Spelling as accepted by Sanny Builder's option name.
        arguments += ["-o", "Decompiler::HexadimalOffsets", "1"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    exit_code, timed_out = None, False
    try:
        settings.parent.mkdir(parents=True, exist_ok=True)
        if had_settings:
            backup.write_bytes(original)
        settings.write_bytes(patched_settings(original, mode_id, str(install_dir)))
        process = subprocess.Popen(arguments, cwd=str(sanny_root), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait()
    finally:
        # Leave the user's Sanny Builder configuration exactly as it was found.
        if had_settings:
            settings.write_bytes(original)
            if backup.exists():
                backup.unlink()
        else:
            if settings.exists():
                settings.unlink()
            if created_data_dir:
                try:
                    settings.parent.rmdir()
                except OSError:
                    pass

    if timed_out:
        raise DevkitError("Sanny Builder did not finish within %g seconds and was stopped" % timeout)
    if exit_code != 0:
        raise DevkitError("Sanny Builder exit code %s" % exit_code)
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise DevkitError("no decompiled output was written")
    after = sha256_file(scm_path)
    if after != before:
        raise DevkitError("the input copy changed during decompilation")
    with open(out_path, "rb") as handle:
        lines = sum(1 for _ in handle)
    return {"schemaVersion": 1, "tool": "sanny_decompile.py " + TOOL_VERSION, "exitCode": 0, "game": game,
            "modeId": mode_id, "hexOffsets": bool(hex_offsets), "inputSha256": after, "inputUnchanged": True,
            "output": str(out_path), "outputBytes": out_path.stat().st_size, "outputLines": lines,
            "outputSha256": sha256_file(out_path), "settingsRestored": True,
            "reminder": "Decompiled script text stays private; record only labels, offsets, opcodes and hashes."}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sanny-dir", required=True)
    parser.add_argument("--game-dir", required=True, help="installation Sanny reads definitions from (read-only)")
    parser.add_argument("--scm", required=True, help="private copy of main.scm or an extracted script")
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--game", default="sa", help="Sanny Builder game identifier (default: sa)")
    parser.add_argument("--mode-id", default="sa_sbl", help="settings.ini section of the edit mode (default: sa_sbl)")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--no-hex-offsets", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        print("note: sanny.exe is a Windows program; this run only works where it can be executed", file=sys.stderr)
    print(json.dumps(decompile(args.sanny_dir, args.game_dir, args.scm, args.output, args.expected_sha256,
                               args.game, args.mode_id, args.timeout, not args.no_hex_offsets), indent=1))


if __name__ == "__main__":
    run(main)

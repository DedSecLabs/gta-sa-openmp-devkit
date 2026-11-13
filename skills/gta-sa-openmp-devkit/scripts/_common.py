"""Shared helpers for the GTA SA open.mp DevKit scripts. Standard library only (Python 3.12+)."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import struct
import sys
import tempfile
from pathlib import Path

TOOL_VERSION = "0.1.2"
MIN_PYTHON = (3, 12)
EXE_NAMES = ("gta_sa.exe", "gta-sa.exe", "gta_sa_compact.exe")
PROFILE_NAME = "gta-sa-openmp-devkit.json"


class DevkitError(Exception):
    """A refusal or invalid input that should be reported without a traceback."""


def python_supported(version=None) -> bool:
    """True when the interpreter meets MIN_PYTHON (the only versions these tools are tested on)."""
    return tuple((version or sys.version_info)[:2]) >= MIN_PYTHON


def run(main) -> None:
    """Run a script entry point; print refusals and file-system errors as one line and exit 2."""
    if not python_supported():
        print("error: these tools need Python %d.%d or newer; this is Python %s"
              % (MIN_PYTHON + (sys.version.split()[0],)), file=sys.stderr)
        sys.exit(2)
    try:
        code = main()
    except (DevkitError, OSError) as error:
        print("error: " + str(error), file=sys.stderr)
        sys.exit(2)
    sys.exit(code or 0)


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hex_(value: int) -> str:
    return "0x%X" % value


def parse_hex(text: str) -> int:
    try:
        return int(str(text).strip(), 16)
    except ValueError:
        raise DevkitError("not a hexadecimal value: %r" % (text,))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha256(text) -> bool:
    return isinstance(text, str) and len(text) == 64 and all(c in "0123456789abcdef" for c in text.lower())


def absolute(path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def is_within(path, root) -> bool:
    """True when path is root or inside it (case-insensitive, as on Windows volumes)."""
    child = os.path.normcase(os.fspath(absolute(path))).lower()
    parent = os.path.normcase(os.fspath(absolute(root))).lower().rstrip("\\/")
    return child == parent or child.startswith(parent + os.sep)


def _names(directory: Path):
    try:
        return {entry.name.lower() for entry in os.scandir(directory)}
    except OSError:
        return set()


def find_install_root(path):
    """Return the nearest directory at or above path that holds a game executable, else None.

    Detection uses the executable's presence only; folder names prove nothing about a build.
    """
    # Check the path as written and with links resolved: a link into data/ must not hide the installation.
    for current in (absolute(path), Path(os.path.realpath(os.fspath(path)))):
        for candidate in [current, *current.parents]:
            if candidate.is_dir() and any(name in _names(candidate) for name in EXE_NAMES):
                return candidate
    return None


def require_outside_install(path, what: str, also=()) -> Path:
    """Refuse a path located in any game installation, or in one of the extra roots."""
    full = absolute(path)
    root = find_install_root(full)
    if root is not None:
        raise DevkitError("%s must be outside a game installation (found one at %s)" % (what, root))
    for extra in also:
        if is_within(full, extra) or is_within(os.path.realpath(full), os.path.realpath(extra)):
            raise DevkitError("%s must be outside %s" % (what, extra))
    return full


def ci_path(root, *parts):
    """Join parts under root ignoring case, so a Windows installation also resolves on other systems."""
    current = Path(root)
    for part in parts:
        direct = current / part
        if direct.exists():
            current = direct
            continue
        try:
            match = next((e.name for e in os.scandir(current) if e.name.lower() == part.lower()), None)
        except OSError:
            match = None
        current = current / (match or part)
    return current


def game_root(path) -> Path:
    root = absolute(path)
    if not root.is_dir():
        raise DevkitError("game directory not found: %s" % root)
    return root


def rel_posix(path, root) -> str:
    return Path(os.path.relpath(path, root)).as_posix()


def write_json(path, document, forbid=()) -> Path:
    """Write JSON atomically (UTF-8, LF) to a location outside any game installation."""
    full = require_outside_install(path, "output path", also=forbid)
    if full.is_dir():
        raise DevkitError("output path is a directory: %s" % full)
    full.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # Exclusive creation avoids following an existing link or colliding with another writer.
        # Keep the temporary on the destination filesystem for atomic replacement on Windows too.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=full.parent, prefix="." + full.name + ".", suffix=".tmp",
                                         delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(document, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, full)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return full


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except OSError as error:
        raise DevkitError("cannot read %s: %s" % (path, error))
    except ValueError as error:
        raise DevkitError("%s is not valid JSON: %s" % (path, error))


def load_profile(start=None):
    """Find gta-sa-openmp-devkit.json at or above start. Returns (path or None, mapping)."""
    current = absolute(start or os.getcwd())
    for candidate in [current, *current.parents]:
        target = candidate / PROFILE_NAME
        if target.is_file():
            data = read_json(target)
            if not isinstance(data, dict):
                raise DevkitError("%s must contain a JSON object" % target)
            return target, data
    return None, {}


# --- Portable Executable facts ------------------------------------------------------------------

def read_pe(path) -> dict:
    """Header facts of a 32-bit PE file. 'valid' is False with a reason for anything else."""
    with open(path, "rb") as handle:
        head = handle.read(65536)
    if len(head) < 64 or head[:2] != b"MZ":
        return {"valid": False, "reason": "no MZ header"}
    pe = struct.unpack_from("<i", head, 0x3C)[0]
    if pe < 0 or pe + 24 > len(head) or head[pe:pe + 4] != b"PE\0\0":
        return {"valid": False, "reason": "no PE signature in the first 64 KiB"}
    machine, count, stamp = struct.unpack_from("<HHI", head, pe + 4)
    opt_size, characteristics = struct.unpack_from("<HH", head, pe + 20)
    opt = pe + 24
    if opt + 72 > len(head):
        return {"valid": False, "reason": "optional header outside the first 64 KiB"}
    magic = struct.unpack_from("<H", head, opt)[0]
    facts = {
        "valid": True,
        "machine": "0x%04X" % machine,
        "architecture": {0x14C: "x86", 0x8664: "x64"}.get(machine, "other"),
        "optionalHeaderMagic": "0x%03X" % magic,
        "characteristics": "0x%04X" % characteristics,
        "timeDateStampRaw": stamp,
        "timeDateStampUtc": datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if magic != 0x10B:
        facts["valid"] = False
        facts["reason"] = "not a 32-bit (PE32) image"
        return facts
    entry, = struct.unpack_from("<I", head, opt + 16)
    base, = struct.unpack_from("<I", head, opt + 28)
    size_image, size_headers, checksum = struct.unpack_from("<III", head, opt + 56)
    facts.update(entryPointRva=hex_(entry), imageBase=hex_(base), sizeOfImage=hex_(size_image),
                 sizeOfHeaders=hex_(size_headers), checksum=hex_(checksum))
    sections = []
    table = opt + opt_size
    for index in range(count):
        at = table + 40 * index
        if at + 40 > len(head):
            facts["sectionTableTruncated"] = True
            break
        name = head[at:at + 8].rstrip(b"\0").decode("latin-1")
        vsize, vaddr, rsize, roff = struct.unpack_from("<IIII", head, at + 8)
        sections.append({"name": name, "virtualAddress": hex_(vaddr), "virtualSize": hex_(vsize),
                         "rawOffset": hex_(roff), "rawSize": hex_(rsize)})
    facts["sections"] = sections
    return facts


def va_to_offset(pe: dict, va: int, length: int):
    """File offset backing [va, va+length) or None when that range is not stored on disk."""
    rva = va - int(pe["imageBase"], 16)
    for section in pe.get("sections", []):
        start = int(section["virtualAddress"], 16)
        backed = min(int(section["virtualSize"], 16), int(section["rawSize"], 16))
        if start <= rva and rva + length <= start + backed:
            return int(section["rawOffset"], 16) + (rva - start)
    return None


def probe(path, pe: dict, va: int, length: int, show_bytes: bool = False) -> dict:
    """Hash a small on-disk byte range at a virtual address. Bytes are emitted only on request."""
    result = {"va": hex_(va), "rva": hex_(va - int(pe["imageBase"], 16)), "length": length,
              "fileOffset": None, "sha256": None, "status": "not-file-backed"}
    offset = va_to_offset(pe, va, length)
    if offset is None:
        return result
    with open(path, "rb") as handle:
        handle.seek(offset)
        data = handle.read(length)
    if len(data) != length:
        result["status"] = "short-read"
        return result
    result.update(fileOffset=hex_(offset), sha256=sha256_bytes(data), status="read")
    if show_bytes:
        result["bytes"] = data.hex(" ")
    return result

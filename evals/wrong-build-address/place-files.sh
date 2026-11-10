#!/usr/bin/env bash
# Generates synthetic fixtures; nothing here is game content.
set -eu
python3 - <<'PY'
import struct, os
dos = bytearray(0x80); dos[0:2] = b"MZ"; struct.pack_into("<i", dos, 0x3C, 0x80)
coff = b"PE\0\0" + struct.pack("<HHIIIHH", 0x14C, 1, 1114702282, 0, 0, 0xE0, 0x10F)
opt = bytearray(0xE0); struct.pack_into("<H", opt, 0, 0x10B); struct.pack_into("<I", opt, 16, 0x1000)
struct.pack_into("<I", opt, 28, 0x400000); struct.pack_into("<III", opt, 56, 0x3000, 0x400, 0)
sec = b".text\0\0\0" + struct.pack("<IIII", 0x1000, 0x1000, 0x200, 0x400) + bytes(16)
os.makedirs("Game", exist_ok=True)
open("Game/gta_sa.exe", "wb").write((bytes(dos) + coff + bytes(opt) + sec).ljust(0x400, b"\0") + bytes(0x200))
PY

#!/usr/bin/env bash
# Generates synthetic fixtures; nothing here is game content.
set -eu
mkdir -p work
python3 -c "open('work/main.scm','wb').write(bytes([0xFF])*64 + bytes([0xA5,0x00,0x04,0x05]) + bytes([0xFF])*64)"

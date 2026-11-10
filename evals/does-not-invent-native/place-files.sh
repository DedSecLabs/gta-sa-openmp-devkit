#!/usr/bin/env bash
# Generates synthetic fixtures; nothing here is game content.
set -eu
mkdir -p include
printf 'native SetPlayerPos(playerid, Float:x, Float:y, Float:z);\nnative SetPlayerInterior(playerid, interiorid);\nnative ApplyAnimation(playerid, const animlib[], const animname[], Float:fDelta, loop, lockx, locky, freeze, time, forcesync = 0);\nforward OnPlayerUpdate(playerid);\n' > include/a_players.inc

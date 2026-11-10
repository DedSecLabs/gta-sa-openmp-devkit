#!/usr/bin/env bash
# Generates synthetic fixtures; nothing here is game content.
set -eu
mkdir -p gta-reversed/source/game_sa
cat > gta-reversed/source/game_sa/Garages.cpp <<'CPP'
// Synthetic test fixture written for this evaluation. Not copied from any project.
void CGarages::InjectHooks() {
    RH_ScopedClass(CGarages);
    RH_ScopedInstall(StoreCarInNearestImpoundingGarage, 0x44A3C0, { .reversed = false });
}

// 0x44A3C0
void CGarages::StoreCarInNearestImpoundingGarage(CVehicle* vehicle) {
    plugin::Call<0x44A3C0, CVehicle*>(vehicle);
}
CPP

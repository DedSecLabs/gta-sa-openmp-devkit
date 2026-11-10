---
name: gta-sa-openmp-devkit
description: Evidence-based research and development for classic GTA San Andreas modding and open.mp/SA-MP servers. Use whenever work depends on how the original game really behaves or what its data really contains - SCM mission scripts, engine code, memory addresses and executable versions, IPL/IDE/DAT data, entrances and interiors, garages, shops, vehicles, peds, HUD or radar - and whenever porting that behavior to open.mp/Pawn or a client ASI/CLEO mod. Use it before asserting "single player does X", before reusing an address or offset from gta-reversed, Plugin-SDK or a forum post, before calling a Pawn native you have not seen declared, and when recording or reviewing research findings, even if the user never says "research". Not for the Definitive Edition, other GTA titles or asset editing.
license: MIT
metadata:
  version: "0.1.1"
compatibility: Bundled scripts need Python 3.12+ (standard library only; validated on 3.12). Optional Sanny Builder decompilation is validated on Windows with version 4.2.0, sa_sbl mode.
---

# GTA SA open.mp DevKit

Evidence-based GTA San Andreas research and open.mp development.

Most wrong mods start from a confident memory: an address that belongs to another executable, a script
behavior nobody read, a native that does not exist. This skill replaces memory with a short loop: find what
is already known, identify the build, look at the right layer, record the claim with its proof, then port it.
Your own recollection of the game counts as *inferred* until a source carries it.

The host project's instructions always win over this skill. Where they are silent, the defaults here apply.

Sanny Builder is needed only for the decompilation workflow. Other research works without it. For local
Windows, authorized remote Windows or a user-run handoff, read [references/scm.md](references/scm.md).
An installation path does not provide remote access. Wine is a possible, unvalidated route.

## The loop

1. **Scope.** Research is needed for anything claimed to be "like single player", any original
   entrance/shop/garage/script/HUD/radar/vehicle/ped rule, and any original value (model, price, handling,
   position, address). Mechanics the project authored itself need none.
2. **Read the project profile and capabilities.** Run `python <skill>/scripts/capabilities.py` from the
   project folder (`<skill>` is the folder holding this file; see Tools). It
   finds `gta-sa-openmp-devkit.json` (where findings live, the game build, pinned references, the target runtime,
   policies) and reports which workflows this machine supports. No profile yet: see
   [references/project-profile.md](references/project-profile.md). A missing tool narrows the research; say
   which path you took instead of filling the gap with a guess.
3. **Search existing findings first.** Search the profile's `findings.file` and `searchPaths` for the topic,
   the original name and the model or file name. Cite a finding that exists; extend it rather than restating
   it. If new evidence disagrees, record a conflict instead of overwriting.
4. **Identify the build.** Addresses, offsets and many data values belong to one executable. Run
   `python <skill>/scripts/identify_build.py <exe>` and state the confidence (*confirmed*, *corroborated*,
   *documented-only*). Never infer version or "original" status from a folder or file name.
5. **Classify the layer, then pick the source.** Behavior often spans layers; say which layer supports each
   claim.

   | Layer | Signs | Read |
   | --- | --- | --- |
   | `scm` | missions, shops, timed or scripted events | [references/scm.md](references/scm.md) |
   | `engine` | physics, camera, HUD drawing, AI, radar: code with no data file | [references/engine-and-exe.md](references/engine-and-exe.md) |
   | `data` | values in `.dat`, `.ide`, `.ipl`, `.cfg`, archives | [references/game-data.md](references/game-data.md) |
   | `runtime` | SA-MP/open.mp, ASI loaders and patches changing stock behavior | [references/openmp.md](references/openmp.md) |

   A name or type number in data does not prove what the engine or a script does with it. A difference
   introduced by a multiplayer client or patch is its own finding, separate from stock behavior.
6. **Record the finding** with build, layer, source and evidence class, in the project's findings file, and
   run `python <skill>/scripts/validate_findings.py <file>`. Format and rules:
   [references/evidence.md](references/evidence.md).
7. **Port it** (when the task is implementation): [references/openmp.md](references/openmp.md) covers
   authority, verifying natives with `check_native.py`, and multiplayer differences. Compiling is not
   proof that the game behaves as intended.
8. **Report** using the structure below.

## Evidence classes

| Class | Meaning | May be implemented as fact? |
| --- | --- | --- |
| `original-observed` | read from original files, or seen in a live probe on the identified build | yes |
| `exe-byte` | established from executable bytes (signature or disassembly) | yes, within the stated limits |
| `source-derived` | from a pinned gta-reversed or Plugin-SDK commit, unchecked against the game | yes, labelled as such |
| `documented` | third-party documentation only | with a stated caveat |
| `inferred` | reasoning, analogy or memory | no: verify it or present it as an authored choice |

## Ground rules

- **Original files are read-only and stay out of repositories.** Record facts and hashes; never copy
  scripts, decompiled source, models, textures or binaries into Git, a finding or a chat reply. The bundled
  scripts refuse to write inside an installation; do the same by hand.
- **Ask before installing tools, downloading assets or starting the game.** The profile's `policies` say
  what the owner already allowed.
- **Cached or extracted copies are not evidence by default.** Use them only if the profile sets
  `cachedEvidence` to `allowed-with-provenance` and you can match each file to a recorded original hash
  ([references/evidence.md](references/evidence.md)).
- **Partial results stay partial.** Every script output has `complete` and coverage notes; carry them into
  the finding. "The scan found nothing" is never "the game does not do this".
- **Do not transfer findings between the classic game and the Definitive Edition**, or between executables,
  without a source for each.

## Tools

The scripts sit next to this file, not in the user's project. In every command, replace `<skill>` with the
folder that contains this `SKILL.md` (for example `.claude/skills/gta-sa-openmp-devkit`), and run it from the
project folder so the profile is found. Every script has `--help`, prints or writes JSON, and exits non-zero
when its result is incomplete; the layer references show typical invocations.

| Script | Use |
| --- | --- |
| `capabilities.py` | what this machine and profile allow |
| `identify_build.py` | executable hash, PE facts, known-build comparison, byte probes |
| `export_manifest.py` | installation metadata and hashes for provenance |
| `export_ipl_records.py` | ENEX entrances or GRGE garages from text IPL files |
| `scan_scm_opcodes.py` | opcode occurrences in private SCM copies (cross-check only) |
| `sanny_decompile.py` | bounded Sanny Builder decompile on Windows |
| `check_native.py` | is a Pawn native/callback declared in the pinned includes |
| `validate_findings.py` | finding records are complete; sources still match their hashes |

## Report structure

End research and implementation answers with these six parts, shortest first. The example is a fictional
entrance, not game data; hashes are shortened here and must be written in full:

```
Answer: SHOPX's entrance record leads to interior 6; the arrival point still needs an in-game check.
Build: unidentified gta_sa.exe (sha256 9e1c…4a7d), confidence documented-only
Evidence: data, original-observed: data/maps/shops/shops.ipl line 2, sha256 41ab…e09c
Not examined: binary and streamed IPLs; nobody checked the arrival point in game
Differences in the target runtime: no single-player script runs on open.mp; the server sets interior and position
Recorded in: docs/research/findings.json#shopx-entrance (or "not recorded" with the reason)
```

# GTA SA open.mp DevKit

**An AI agent skill for GTA San Andreas modding and open.mp/SA-MP server development.**

AI coding assistants are confident about San Andreas and often wrong: a memory address from a different
`gta_sa.exe`, an entrance "copied from single player" that drops players through the floor, a Pawn native
that doesn't exist. With this skill, your agent checks first. It reads your own game files, identifies your
executable from its bytes, verifies natives against the includes you compile with, and tells you what it
could not check.

## Install

```bash
npx skills add DedSecLabs/gta-sa-openmp-devkit
```

Works with agents that support [Agent Skills](https://github.com/agentskills/agentskills), such as Claude
Code and Codex. Or copy the `skills/gta-sa-openmp-devkit/` folder into your project's `.claude/skills/` or
`.agents/skills/` folder.

## Versions and updates

For a tested checkpoint rather than the current default branch, install a version tag:

```bash
npx skills add DedSecLabs/gta-sa-openmp-devkit@v0.1.1 --skill gta-sa-openmp-devkit
```

For an unpinned installation, check for updates and update this skill with:

```bash
npx skills check
npx skills update gta-sa-openmp-devkit
```

To change a pinned installation, explicitly install the desired tag with `skills add` again. Keep your
project profile and findings outside the installed skill folder so replacing it preserves your research.

Versions identify the skill instructions and bundled tools together: patches (`0.1.x`) fix behavior without
changing interfaces, while minor versions add capabilities or document migrations for breaking changes
during `0.x`. Published tags stay attached to their original commits. The tools' version in
`scripts/_common.py` is authoritative; CI checks the skill metadata and latest changelog entry against it.
GitHub Release pages and separate download bundles are not required.

## What you need

- An AI coding agent with skill support.
- **Python 3.12 or newer** for the bundled tools.
- **Your own PC copy of classic GTA San Andreas** for anything that reads game files. The Definitive
  Edition is not supported.
- **Optional:** [Sanny Builder](https://sannybuilder.com/) on Windows, only if you want your agent to read the
  game's mission scripts. Everything else works without it.

## Using it

Ask your agent as you normally would. The skill switches on by itself for GTA SA work, for example:

- *"Make /enter work like the single-player Ammu-Nation entrance on my open.mp server."*
- *"A forum post says this function is at 0x44AA50. Is that right for my gta_sa.exe?"*
- *"Is there an open.mp native to change a player's run speed?"*
- *"How does the original game decide which impound garage a car goes to?"*

What changes with the skill:

- The agent tells you **where each fact came from**: file, line and hash, a pinned source commit, or "not
  verified".
- It **identifies your executable** before trusting an address, and says so when the build is unknown.
- It checks **natives and callbacks against your includes** instead of inventing them.
- It flags **multiplayer differences**: single-player scripts don't run on a server, and entrance records
  are not safe arrival points.
- It ends with **what it didn't examine**, so you know what still needs testing in game.

For repeated work, let the agent create a `gta-sa-openmp-devkit.json` in your project with your game path
and include folders. Ask it to "set up the GTA SA DevKit profile"; the template is in the skill's `assets/`.

## What's inside

| Tool | What it does |
| --- | --- |
| `capabilities.py` | Reports what your machine and project setup allow, before research starts |
| `identify_build.py` | Hashes `gta_sa.exe` and reads its header, so addresses are matched to the right build |
| `export_manifest.py` | Records your installation's files as hashes, for traceable research |
| `export_ipl_records.py` | Extracts entrances (ENEX) and garages (GRGE) from the map files |
| `scan_scm_opcodes.py` | Searches private copies of the mission scripts for a command |
| `sanny_decompile.py` | Runs Sanny Builder to decompile the mission scripts (Windows) |
| `check_native.py` | Checks whether a Pawn native, callback or `#define` exists in your includes |
| `validate_findings.py` | Checks recorded research notes, and flags ones whose source files changed |

Your agent runs these for you. To run one yourself, for example to check a native:

```bash
python <skill>/scripts/check_native.py SetPlayerInterior --include-dir <your-includes-folder>
```

`<skill>` is where the skill was installed, such as `.claude/skills/gta-sa-openmp-devkit`.

## When the game is on another computer

A common setup: your agent and server run on Linux, and GTA San Andreas is on your Windows PC. The skill
handles this explicitly. The agent uses an already-authorized connection to that PC if you have one;
otherwise it gives you the exact command to run there and asks for the result. A Windows path alone does
not give the agent access. Details are in the [script reference](skills/gta-sa-openmp-devkit/references/scm.md).

## Limitations

- **Classic PC GTA San Andreas only.** No Definitive Edition, other GTA games, or model and texture editing.
- **Sanny Builder** was tested with version 4.2.0 (`sa_sbl` mode) on Windows. Other versions, and Linux via
  Wine, are untested.
- **Map data:** only the text map files are read. Binary and streamed map files are skipped, so a missing
  record isn't proof it doesn't exist.
- **The native check reads include files as text.** It doesn't evaluate `#if` conditions; anything behind
  one is reported as `conditional` for you to check. Enum members and constants aren't detected.
- **Your build shows as "unknown" at first.** No executable fingerprints ship with the skill; you can keep
  your own record privately ([how](skills/gta-sa-openmp-devkit/references/engine-and-exe.md#private-build-records)).
- **Measured benefit is small so far.** In five test cases, answers met 18 of 18 criteria with the skill
  and 17 of 18 without. That's one run per case; see the [evaluation](evals/RESULTS.md).

The tools are tested on Linux, Windows and macOS with Python 3.12 and 3.13.

## No game content

This repository contains no game files, decompiled scripts or code from the game. The tools read your own
installation and produce hashes and facts. Keep decompiled scripts and game files out of public repositories.

Not affiliated with or endorsed by Rockstar Games, Take-Two Interactive, or the open.mp, SA-MP,
gta-reversed, Plugin-SDK or Sanny Builder projects.

## Contributing

```bash
python -m unittest discover -s tests -v
```

The skill itself is `skills/gta-sa-openmp-devkit/`. `tests/` covers the tools, and `evals/` holds the
behavior test cases; neither is installed for users. All test fixtures are generated, so never add game
files to the repository. Changes are listed in the [changelog](CHANGELOG.md).

## License

[MIT](LICENSE) for the skill text and tools. Game content and third-party tools are not included or
relicensed.

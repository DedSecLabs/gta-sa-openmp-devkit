# GTA SA open.mp DevKit

**Evidence-based GTA San Andreas research and open.mp development.** An agent skill (Claude Code, Codex and
other [Agent Skills](https://github.com/agentskills/agentskills) clients) that guides an AI assistant to verify
original-game behavior before building a mod or gamemode around it.

> **v0.1.0 — initial release.** See [Limitations](#limitations) and the [behavior evaluation](evals/RESULTS.md).

Not affiliated with or endorsed by Rockstar Games, Take-Two Interactive, or the open.mp, SA-MP, gta-reversed,
Plugin-SDK or Sanny Builder projects. Contains no game files, decompiled scripts or executable code from the
game; the tools read your own installation and emit hashes and facts.

## What it changes

The skill supplies a repeatable research workflow and tools for it. It directs the assistant to:

1. looks for research the project already has;
2. identifies the executable from its bytes, never its folder name;
3. classifies the behavior (script, engine, data, multiplayer runtime) and reads the matching source;
4. records each claim with build, source and an evidence class, and validates the record;
5. ports it to open.mp/Pawn with the API checked against the includes actually used;
6. reports what it did not examine.

## Supported workflows (v0.1.0)

| Workflow | Tool | Platform |
| --- | --- | --- |
| Identify an executable and compare it with recorded builds | `identify_build.py` | any |
| Record an installation's contents as hashes (provenance) | `export_manifest.py` | any |
| Extract entrance (ENEX) and garage (GRGE) records from text IPL files | `export_ipl_records.py` | any |
| Cross-check SCM opcode occurrences in private script copies | `scan_scm_opcodes.py` | any |
| Decompile a private SCM copy with Sanny Builder, non-interactively | `sanny_decompile.py` | Windows (validated with Sanny Builder 4.2.0) |
| Check that a Pawn function, callback or `#define` is declared in your includes | `check_native.py` | any |
| Validate finding records and detect findings whose source files changed | `validate_findings.py` | any |
| Report what the current machine and project profile allow | `capabilities.py` | any |
| Engine research with gta-reversed, Plugin-SDK and executable bytes | procedure only | any |
| Porting a verified finding to open.mp / SA-MP | procedure + `check_native.py` | any |

**Out of scope:** the Definitive Edition, other GTA titles, model/texture/map editing, automated
disassembly, live memory inspection, binary IPLs and IPLs streamed from archives, and runtime-specific
guidance for MTA or CLEO (the research method applies; the porting reference covers open.mp/SA-MP only).

## Install

Requires Python 3.12+ (standard library only). Python 3.12 is the validated version; older versions are
outside this release's support claim. Python is needed for the tools, not for reading the research guidance.

```bash
DISABLE_TELEMETRY=1 npx skills add DedSecLabs/gta-sa-openmp-devkit --skill gta-sa-openmp-devkit
```

or copy `skills/gta-sa-openmp-devkit/` into your project's skills folder (`.claude/skills/`, `.agents/skills/`).
Then copy `assets/project-profile.template.json` from the installed skill folder to your project root as
`gta-sa-openmp-devkit.json` and fill in what applies. The skill works without a profile, with conservative defaults.

## Sanny Builder: optional script decompilation

Sanny Builder is useful when a question requires reading original mission-script control flow. It is not
required for the skill's other tools or for reusing applicable, verified findings. The validated integration
uses Sanny Builder 4.2.0 (`sa_sbl`) on Windows; GTA need not be running.

- **Local Windows:** run Python and Sanny against private copies of the user's scripts.
- **Agent elsewhere, Windows accessible:** reuse an already-authorized connection to run the tools on
  Windows. An installation path alone does not grant access or connect the machines.
- **No remote access:** the user runs the documented Windows command and returns metadata and focused
  findings. Full decompiled scripts remain in the private workspace.

See the [SCM reference](skills/gta-sa-openmp-devkit/references/scm.md) for setup, the command and verification.
Linux/Wine is a possible route reported by users, but is unvalidated for this wrapper. No Wine installation
or automatic remote-access setup is included. Machine-specific paths and credentials do not belong in the
public repository.

## Three worked examples

Values in angle brackets are yours; nothing below is a fact about the game. `<skill>` is the folder the skill
was installed to, for example `.claude/skills/gta-sa-openmp-devkit` or `.agents/skills/gta-sa-openmp-devkit`. Run the
commands from your project folder.

**1. "Is this address valid for my game?"**

```bash
python <skill>/scripts/identify_build.py "<install>/gta_sa.exe" --probe 0x<VA>
```

The output gives the file's SHA-256, PE image base and whether it equals a recorded build. If `identity.match`
is `none`, an address taken from another build is only a lead: the assistant says so instead of patching.

**2. "Use the original entrance for this interior on my server."**

```bash
python <skill>/scripts/export_ipl_records.py --game-dir "<install>" --section enex --output research/enex.json
```

Each record carries its IPL path, line and file hash. The assistant cites those, explains that the record is a
portal volume rather than a safe arrival point, writes the Pawn, and lists the arrival position as needing an
in-game check.

**3. "Record what we learned so nobody redoes it."**

```bash
python <skill>/scripts/validate_findings.py research/findings.json --verify-files "<install>"
```

A finding without a source that can carry its evidence class is rejected. A finding whose source file has
changed is reported as stale, and one whose source file cannot be found as missing; either makes the command
exit non-zero, so an unverified finding never passes as verified.

## Repository layout

```
skills/gta-sa-openmp-devkit/
  SKILL.md        the loop, evidence classes, ground rules (loaded when the skill triggers)
  references/     one file per layer, loaded only when that layer is involved
  scripts/        standard-library Python tools
  assets/         project profile template, findings example, known-builds table
evals/            behavior test cases with synthetic fixtures (not installed with the skill)
tests/            unit tests for the scripts, package hygiene and a clean-project installation
```

## Development

```bash
python -m unittest discover -s tests -v
```

To run the behavior cases with Claude Code's evaluator, copy `evals/` into `skills/gta-sa-openmp-devkit/` first.
All fixtures are generated by the tests. Do not add game files, decompiled scripts or executable bytes to
this repository, in tests or anywhere else.

## Limitations

- **Tested on Linux (Python 3.12.3) and Windows 11 (Python 3.12.14): 47 tests pass on both, none skipped.
  These are local validation runs.** [Hosted CI](https://github.com/DedSecLabs/gta-sa-openmp-devkit/actions/workflows/ci.yml)
  is configured for Linux, Windows and macOS on Python 3.12 and 3.13; consult the linked runs for each
  revision's results. Local macOS execution has not been performed.
- **Sanny Builder integration was validated once**, with Sanny Builder 4.2.0 in its `sa_sbl` mode on Windows 11:
  a real decompile of a private `main.scm` copy exited 0, the input hash was unchanged, and `settings.ini` was
  restored byte-for-byte. Other Sanny Builder versions and edit modes are untested; treat them as
  experimental and check the result fields (`inputUnchanged`, `settingsRestored`) on your first run.
- **Decompile comparison:** the prior and corrected-wrapper outputs each contain 534,075 lines. The 548-byte
  reduction is entirely accounted for by 274 `SeatId.FrontRight` -> `SeatId.BikeRear` substitutions (both
  value 0) and nine `WheelId.BikeRear` -> `WheelId.RearLeft` substitutions (both value 1, equal-length names).
  Normalizing just these aliases makes the outputs byte-identical. Values were checked in the installed
  `data/sa_sbl/enums.txt` (SHA-256 `9a8a1eea9ceff76e232d833de92b6f9e1d350336e145243a7058583bd0797b4e`).
  This establishes equivalent text under those definitions, not why Sanny chose different aliases or an
  in-game behavior test. The private outputs were read in place and left unchanged.
- **An interrupted decompile** (process killed) leaves Sanny Builder's settings patched until the next run of
  the wrapper, which restores them from its backup file.
- **Installation checks:** the skill was installed from a local source into an empty project with the
  Skills CLI. The documented commands are also checked against a standalone installed copy by the test
  suite. The published repository uses the same standard layout.
- **`check_native.py` does not evaluate preprocessor conditions** other than literal `0`/`1`; a declaration
  dependent on an unresolved branch or a possible `#endinput` remains `conditional`. Include guards are not
  assumed open. Check against actual compiler defines/include order; a textual match does not prove runtime
  availability. Enum members, const variables and multiline declarations are not detected.
- **Ten offline behavior runs were completed:** five cases with the skill and five without, using fresh
  contexts of the same configured model. The rubric scored 18/18 with the skill and 17/18 without. This small,
  manually graded sample does not establish a general reliability, speed or token-efficiency advantage;
  see [method, results and limitations](evals/RESULTS.md).
- **The known-builds table ships empty.** Identification still reports PE facts and hashes; use a private
  local table for recorded builds. See [build-record guidance](skills/gta-sa-openmp-devkit/references/engine-and-exe.md#private-build-records).
- **ENEX field names beyond the first fourteen** follow community documentation and are not verified.
- **No disassembler is bundled**; executable-byte work beyond hashing a range needs your own tool.

## License

[MIT](LICENSE) for the original skill text and tools. GTA game content and third-party tools are not
included or relicensed. Keep original scripts and decompiled output outside public repositories.

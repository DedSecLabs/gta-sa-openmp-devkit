# Changelog

## 0.1.1

- Create JSON output through an exclusively created temporary file, preventing pre-existing temporary
  symlinks or hard links from overwriting game files. Failed writes preserve the previous output and
  remove their temporary file.
- Reject fractional ENEX interior IDs and flags instead of silently truncating them into apparent facts.
  Integral decimal representations remain supported; malformed rows make the export incomplete.
- Align the tool version, skill metadata and changelog; CI checks their agreement. Document stable tagged
  installation and update commands. Version tags identify tested revisions; GitHub Release pages are optional.

## 0.1.0

- Portable research method extracted into one skill with per-layer references and a project profile.
- Tools rewritten as standard-library Python with synthetic-fixture tests.
- Sanny Builder wrapper: the game identifier is no longer overwritten by the installation path, and
  `settings.ini` is restored after every run, including failures and timeouts.
- All tools refuse to write inside a game installation and report partial results explicitly.
- Finding records are validated; findings whose source files changed are reported as stale.
- Review round 1: installation detection follows links; manifests of folders without an executable are
  incomplete; finding sources cannot point outside the installation; declaration checks no longer match
  loose `const`/`enum` lines; Sanny settings are matched case-insensitively, UTF-16 settings are refused and
  an interrupted run is repaired on the next one; scan output states whether script.img was covered; tools
  leave the installed skill folder unchanged; file-system errors print one line instead of a traceback.
- Review round 2: the decompile wrapper refuses an output that is, or aliases, its input; the declaration
  checker ignores comments and reports `declared`, `conditional`, `disabled` or `not-found`; finding
  verification is reported separately from structure and missing sources exit non-zero; wrong JSON types are
  reported instead of crashing; every documented command is addressed through `<skill>` and tested from a
  consuming project.
- Validated on Windows 11: unit suite, and one real Sanny Builder 4.2.0 decompile.
- Review round 3: declaration uncertainty survives branch chains, conditional `#endinput` and later defines;
  true fallback branches exclude subsequent alternatives. Include guards retain their conditions.
- Sanny setup documents local Windows, authorized remote execution and a user-run handoff; Wine remains
  unvalidated. Python support is narrowed to 3.12+ with 3.12 validated, instead of an untested 3.9 minimum.
- Released as GTA SA open.mp DevKit (`gta-sa-openmp-devkit`) under MIT; personal executable fingerprints
  are omitted. A larger reviewed findings library is deferred. Five paired offline behavior cases are recorded
  separately from the tool tests, with their limitations.
- Tools refuse to run on Python older than 3.12 with a one-line error, and `capabilities.py` reports
  `pythonSupported`. `SKILL.md` shows a filled-in example answer instead of a bare template. The README is
  rewritten for users: install, requirements, example requests, and current limitations.

### Validation notes

- Decompile comparison (Sanny Builder 4.2.0, `sa_sbl`): the outputs of the earlier wrapper and the corrected
  one each contain 534,075 lines. The 548-byte difference is entirely accounted for by 274
  `SeatId.FrontRight` -> `SeatId.BikeRear` substitutions (both value 0) and nine `WheelId.BikeRear` ->
  `WheelId.RearLeft` substitutions (both value 1, equal-length names). Normalizing just these aliases makes
  the outputs byte-identical. Values were checked in the installed `data/sa_sbl/enums.txt` (SHA-256
  `9a8a1eea9ceff76e232d833de92b6f9e1d350336e145243a7058583bd0797b4e`). This shows equivalent text under those
  definitions, not why Sanny chose different aliases, and is not an in-game behavior test.
- An interrupted decompile (process killed) leaves Sanny Builder's settings patched until the wrapper's next
  run, which restores them from its backup file.

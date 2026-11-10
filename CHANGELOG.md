# Changelog

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

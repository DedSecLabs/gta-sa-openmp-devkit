# Evidence: recording findings

A finding is one claim that could be proven wrong, with enough attached that someone else can check it
without asking you. The format exists so that later work can reuse a finding safely, or see at once that it
cannot.

## Finding record

Stored in the project's findings file (`{"schemaVersion": 1, "findings": [...]}`), see
[the example](../assets/findings.example.json).

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | lowercase words joined by hyphens; stable, never reused |
| `claim` | yes | one behavior or value |
| `layer` | yes | `scm`, `engine`, `data` or `runtime` |
| `evidenceClass` | yes | see below |
| `build` | yes | `label`, `confidence`, and `exeSha256` when known |
| `sources` | yes | list; may be empty only for `inferred` |
| `notExamined` | for `inferred`; recommended always | what was skipped, which parts of a routine were not read, partial tool coverage |
| `multiplayerNotes` | no | where the target runtime differs |
| `implementation` | no | `status`: `none`, `planned`, `implemented`; `where` |
| `conflictsWith` | no | ids of findings this one disagrees with |

Sources by `type`:

- `file`: `path` (installation-relative), `sha256`, optional `line`.
- `repository`: `url`, `commit` (a hash, not a branch), `path`, optional `line`.
- `executable`: `sha256` of the executable, `addressKind` (`va`, `rva` or `fileOffset`), `address`, optional
  `length`, `sliceSha256`, `tool`.
- `probe`: `date`, `observer`, `description` of what was seen in the running game.
- `documentation`: `title`, `retrieved` date, optional `url`.

## What each class needs

| Class | Needs | Why |
| --- | --- | --- |
| `original-observed` | a `file` or `probe` source | someone read the original or watched the game |
| `exe-byte` | an `executable` source and `build.exeSha256` | an address means nothing without the file it belongs to |
| `source-derived` | a `repository` source at a commit | reconstructions change; the commit pins what you read |
| `documented` | a `documentation` source | so the reader can judge the documentation |
| `inferred` | `notExamined`; cannot be `implemented` | reasoning is a lead, not a fact |

Choose the class by the weakest link the claim depends on. Reading a function in gta-reversed and matching
sixteen bytes at its address is `source-derived` for the behavior and `exe-byte` only for "this address holds
these bytes". Record two findings if both matter.

These classes describe original-game evidence. They say nothing about whether your own implementation was
tested or accepted; keep that in the project's own status tracking.

## Version confidence

- `confirmed`: the executable hash equals a documented reference build.
- `corroborated`: several independent byte signatures agree with the label.
- `documented-only`: the label is stated somewhere but unchecked.

## Reuse and staleness

Before reusing a finding, check that it still applies:

- same executable hash as the build you are working on (for `exe-byte` and most `engine` findings);
- same pinned commit, or re-read the cited lines at the new one;
- for `file` sources, run `python <skill>/scripts/validate_findings.py <file> --verify-files <installDir>`. A `stale`
  line means the source file no longer matches: re-derive the finding. A `missing` line means the file was
  not found, so nothing was verified. Either way the command exits non-zero; only `verification: complete`
  means the sources were checked.

When the checks pass, cite the finding and move on: re-doing verified research costs time and invites a
second, slightly different answer.

## Conflicts

When two sources disagree, add both findings and link them with `conflictsWith`. Say which governs and why
(usually: the stronger class on the identified build). Do not delete the losing finding; a later reader needs
to know the disagreement was seen.

## Cached and extracted copies

Default: not evidence. If the profile allows `allowed-with-provenance`, a cached file may be used once you
record its path, SHA-256, installation-relative origin, build and confidence, extraction method and date, and
whether the set is complete. The strongest proof is a hash equal to one already recorded from the original
installation. Material of unknown origin (repacks, mods, multiplayer client files) is not original-game
evidence until matched that way. Never cite a cache path alone.

## What never goes into a finding

Decompiled script text, executable bytes beyond a short signature, complete data files, models or textures.
Record the location, the hash and a summary of what the bytes or lines establish.

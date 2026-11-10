# Project profile

The skill is portable; the project is not. `gta-sa-openmp-devkit.json` at the project root tells the skill where this
project keeps things, so nothing about one team's layout is baked into the method.

Start from [the template](../assets/project-profile.template.json). If the project has no profile, propose
one to the user, filled with what you can see, and ask for the rest; do not guess game paths.

Paths apply on the machine running the tools. A remote Windows path is not accessible from Linux merely
because it is recorded here. Keep machine-specific profiles private; do not store credentials in them.
For Windows execution and a manual handoff, see [scm.md](scm.md).

| Key | Meaning |
| --- | --- |
| `findings.file` | The findings JSON this project maintains (validated by `validate_findings.py`). One file, or a folder of files. |
| `findings.searchPaths` | Folders to search for existing research before starting. |
| `findings.recordNarrativeIn`, `decisionsIn` | Where prose write-ups and implementation decisions belong. Use the project's existing documents; do not start parallel notes. |
| `game.installDir` | The reference installation, read-only. Leave empty if the agent has no access. |
| `game.build` | Label, confidence and executable SHA-256 from `identify_build.py`. |
| `references.gtaReversed`, `pluginSdk` | Local checkout path, URL and the pinned commit used for citations. |
| `tools.sannyDir` | Sanny Builder folder (Windows). |
| `tools.privateWorkspace` | Folder outside any installation holding private copies of `main.scm` and `script.img`, and decompile output. Never a Git working tree. |
| `target.runtime`, `version`, `includeDirs` | The runtime being developed for and the include folders the build really uses. |
| `target.clientPatches` | Client-side components that change stock behavior (multiplayer client, ASI loader, patches), with versions. |
| `policies.cachedEvidence` | `forbidden` (default) or `allowed-with-provenance`. |
| `policies.installTools`, `startGame` | `ask` (default), `allowed` or `forbidden`. |

## Precedence

1. The host project's own instruction files (for example `AGENTS.md` or `CLAUDE.md`) and the user.
2. The profile.
3. This skill's defaults.

If two of them disagree, follow the higher one and mention the disagreement once. Example: a project that
forbids reading a cache folder overrides a profile that allows cached evidence.

## Without a profile

The method still applies. Tell the user which defaults you used: cached evidence forbidden, ask before
installing or starting anything, findings returned in the answer instead of written to a file.
